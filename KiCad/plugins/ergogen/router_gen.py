from typing import Union, cast
import pcbnew
from collections import defaultdict
import decimal
import math
from .helper import get_logger
logger = get_logger(__name__)


def log_track(track: pcbnew.PCB_TRACK, prefix=""):
    logger.debug(f'{prefix}{track.GetTypeDesc()}: NC:{track.GetNetCode()},NN:{track.GetNetname()},({pcbnew.ToMM(track.GetX())},{pcbnew.ToMM(track.GetY())})->({pcbnew.ToMM(track.GetEndX())},{pcbnew.ToMM(track.GetEndY())}), {track.m_Uuid.AsString()}')  # noqa: E501


class SelectionAnalysis:
    fp_count: int
    fps: set[str]
    default_fp: str
    tracks_count: int
    vias_count: int
    nets: set[str]
    unsupported_count: int
    unsupported_types: set[str]

    def __init__(self):
        self.fp_count = 0
        self.fps = set()
        self.default_fp = ""
        self.tracks_count = 0
        self.vias_count = 0
        self.nets = set()
        self.unsupported_count = 0
        self.unsupported_types = set()


class RouterGen:
    board: pcbnew.BOARD
    connectivity: pcbnew.CONNECTIVITY_DATA

    def __init__(self):
        self.board = pcbnew.GetBoard()
        self.connectivity = self.board.GetConnectivity()

    def get_selection_analysis(self) -> SelectionAnalysis:
        sel_analysis = SelectionAnalysis()
        selected_items = pcbnew.GetCurrentSelection()
        item: pcbnew.BOARD_ITEM
        largest_fp_area = 0
        for item in selected_items:
            if not item.IsSelected():
                continue
            item_type = item.GetTypeDesc()
            if item_type == 'Footprint':
                sel_analysis.fp_count += 1
                fp: pcbnew.FOOTPRINT = item.Cast()
                sel_analysis.fps.add(fp.GetReferenceAsString())
                if fp.GetArea() > largest_fp_area:
                    sel_analysis.default_fp = fp.GetReferenceAsString()
                    largest_fp_area = fp.GetArea()
                for pad in fp.Pads():
                    if self.connectivity.GetConnectedTracks(pad).size() != 0:
                        sel_analysis.nets.add(pad.GetNetname())
            elif item_type == 'Track':
                sel_analysis.tracks_count += 1
                track: pcbnew.PCB_TRACK = item.Cast()
                sel_analysis.nets.add(track.GetNetname())
            elif item_type == 'Via':
                sel_analysis.vias_count += 1
            else:
                sel_analysis.unsupported_count += 1
                sel_analysis.unsupported_types.add(item_type)
        return sel_analysis

    def get_routes_yaml(self, routes, tab_size=2, fp_sec_name:str = "<routes_footpring_name>", filter:str ="true") -> str:
        yaml = ""
        yaml += 0 * tab_size * " " + "footprints:\n"
        yaml += 1 * tab_size * " " + f'{fp_sec_name}:\n'
        yaml += 2 * tab_size * " " + "what: router\n"
        yaml += 2 * tab_size * " " + f'where: {filter}\n'
        yaml += 2 * tab_size * " " + "params:\n"
        yaml += 3 * tab_size * " " + "locked: false\n"
        yaml += 3 * tab_size * " " + "routes:\n"
        for route in routes:
            yaml += 4 * tab_size * " " + '- ' + route + '\n'
        return yaml


    def get_selection_router_config(self, ref_fp_name: str, nets_map: dict[str, str], footprint_tracks: bool, selected_tracks_vias: bool,
                                    include_locked_tracks_vias:bool, 
                                    place_nets:bool = True, tab_size: int = 2, fp_sec_name:str= "", where_filter:str = "true") -> str:
        selected_items = pcbnew.GetCurrentSelection()
        footprints: list[pcbnew.FOOTPRINT] = []
        ref_fp: Union[pcbnew.FOOTPRINT, None] = None
        all_tracks: dict[str, pcbnew.PCB_TRACK] = {}
        all_vias: dict[str, pcbnew.PCB_VIA] = {}

        for item in selected_items:
            if item.GetTypeDesc() == 'Footprint':
                footprints.append(item.Cast())
                if item.GetReferenceAsString() == ref_fp_name:
                    ref_fp = item

        if len(footprints) == 0:
            result = 'No footprints in selection, at least one needed for reference position'
            logger.debug("@Result: " + result)
            return result

        # Add tracks and vias through footprint if requested
        if footprint_tracks:
            all_tracks, all_vias = self.get_footprints_tracks(footprints)

        # Add explicitly selected items if requested
        if selected_tracks_vias:
            for item in selected_items:
                if item.GetTypeDesc() == 'Track':
                    all_tracks[item.m_Uuid.AsString()] = item.Cast()
                elif item.GetTypeDesc() == 'Via':
                    all_vias[item.m_Uuid.AsString()] = item.Cast()

        # Remove locked tracks/vias if needed
        if not include_locked_tracks_vias:
            all_tracks = {k: v for k,v in all_tracks.items() if not v.IsLocked() }
            all_vias = {k: v for k,v in all_vias.items() if not v.IsLocked() }

        if len(all_tracks) == 0 and len(all_vias) == 0:
            result = 'No tracks or vias resulted from Selection in KiCad and Route Specifications'
            logger.debug("@ Result: " + result)
            return result

        if ref_fp is not None:
            routes = self.process_tracks(all_tracks, all_vias, ref_fp.GetX(), ref_fp.GetY(),
                                         ref_fp.GetOrientationDegrees(), place_nets, nets_map)
            result = self.get_routes_yaml(routes, tab_size, fp_sec_name, where_filter)
            logger.debug("@ Result:\n" + result)
            return result
        else:
            result = 'No reference footprint selected'
            logger.debug("@ Result: " + result)
            return result

##################################################################

    def get_footprints_tracks(self, footprints: list[pcbnew.FOOTPRINT]) -> tuple[dict[str, pcbnew.PCB_TRACK], dict[str, pcbnew.PCB_VIA]]:

        def add_connected_tracks(item: pcbnew.BOARD_CONNECTED_ITEM):
            nonlocal tracks_by_uuid
            nonlocal vias_by_uuid
            nonlocal pads_by_uuid

            item_uuid = item.m_Uuid.AsString()
            if item_uuid in tracks_by_uuid or item_uuid in vias_by_uuid or item_uuid in pads_by_uuid:
                return
            if item.GetTypeDesc() == 'Pad':
                pads_by_uuid[item_uuid] = item.Cast()
            elif item.GetTypeDesc() == 'Track':
                tracks_by_uuid[item_uuid] = item.Cast()
            elif item.GetTypeDesc() == 'Via':
                vias_by_uuid[item_uuid] = item.Cast()
            else:
                assert True, "Found unsupported item when collecting tracks, shouldn't reach here"

            # First get directly connected tracks/vias
            connected_tracks = self.connectivity.GetConnectedTracks(item)
            track: pcbnew.PCB_TRACK
            for track in connected_tracks:
                add_connected_tracks(track)
            # Next get indirectly through pads
            connected_pads = self.connectivity.GetConnectedPads(item)
            for pad in connected_pads:
                add_connected_tracks(pad)

        tracks_by_uuid: dict[str, pcbnew.PCB_TRACK] = {}
        vias_by_uuid: dict[str, pcbnew.PCB_VIA] = {}
        pads_by_uuid: dict[str, pcbnew.PAD] = {}
        for footprint in footprints:
            for pad in footprint.Pads():
                add_connected_tracks(pad)
        return (tracks_by_uuid, vias_by_uuid)

##################################################################

    def process_tracks(self,
                       tracks_by_uuid: dict[str, pcbnew.PCB_TRACK],
                       vias_by_uuid: dict[str, pcbnew.PCB_VIA],
                       ref_x,
                       ref_y,
                       orientation: float,
                       place_nets: bool = True,
                       nets_map: dict[str, str] = {}):

        def get_tracks_by_pos() -> tuple[dict[tuple[int, int], list[pcbnew.PCB_TRACK]], dict[tuple[int, int], list[pcbnew.PCB_VIA]]]:
            tracks_by_pos: dict[tuple[int, int], list[pcbnew.PCB_TRACK]] = defaultdict(list)  # noqa: E501
            vias_by_pos: dict[tuple[int, int], list[pcbnew.PCB_VIA]] = defaultdict(list)  # noqa: E501
            for track in tracks_by_uuid.values():
                track_start = (track.GetX(), track.GetY())
                track_end = (track.GetEndX(), track.GetEndY())
                if track.GetTypeDesc() == 'Track':
                    tracks_by_pos[track_start].append(track.Cast())
                    if track_end != track_start:
                        tracks_by_pos[track_end].append(track.Cast())
                elif track.GetTypeDesc() == 'Via':
                    vias_by_pos[track_start].append(track.Cast())
            return tracks_by_pos, vias_by_pos


        def pos_is_connected_to_track_or_via(pos: tuple[int,int]) -> bool:
            # Need to do exact match, because for route position purpose, even if tracks are connected
            # but not on exact point, then need to start a new route (or place 'x' command)
            return len(tracks_by_pos[pos])+len(vias_by_pos) > 1

        def pos_is_connected_to_track(pos: tuple[int,int]) -> bool:
            # Need to do exact match, because for route position purpose, even if tracks are connected
            # but not on exact point, then need to start a new route (or place 'x' command)
            return len(tracks_by_pos[pos]) > 1


        def pos_is_connected_to_single_track(pos: tuple[int,int]) -> bool:
            return len(tracks_by_pos[pos]) == 1

        def distance(pos1: tuple[int, int], pos2: tuple[int, int]):
            dx = cast(float, pcbnew.ToMM(abs(pos1[0]-pos2[0])))
            dy = cast(float, pcbnew.ToMM(abs(pos1[1]-pos2[1])))
            distance = math.sqrt(dx*dx + dy*dy)
            return distance

# --- Start of set of unused functions, in case needed in the future --------------------------------------------------

        def dangling_test_with_tolernace(track: pcbnew.PCB_TRACK, test_type: int) -> bool:
            tolerance: int = cast(int, pcbnew.FromMM(0.25)) 
            accumulated_status = 0
            connected_tracks = self.connectivity.GetConnectedTracks(track)
            connected_track: pcbnew.PCB_TRACK
            for connected_track in connected_tracks:
                if connected_track.GetTypeDesc() != "Track":
                    continue
                if connected_track.m_Uuid.AsString() not in tracks_by_uuid:
                    continue
                log_track(connected_track, "track_start_is_dangling: testing against track")
                accumulated_status = accumulated_status | track.IsPointOnEnds(connected_track.GetPosition(), tolerance)
                accumulated_status = accumulated_status | track.IsPointOnEnds(connected_track.GetEnd(), tolerance)
                if (accumulated_status & test_type) == test_type:
                    return False
            return True

        def track_start_is_dangling(track: pcbnew.PCB_TRACK) -> bool:
            return dangling_test_with_tolernace(track, pcbnew.STARTPOINT)

        def track_end_is_dangling(track: pcbnew.PCB_TRACK) -> bool:
            return dangling_test_with_tolernace(track, pcbnew.ENDPOINT)

        def track_either_endpoint_is_dangling(track: pcbnew.PCB_TRACK) -> bool:
            return dangling_test_with_tolernace(track, pcbnew.STARTPOINT | pcbnew.ENDPOINT)

        def pos_on_track_start(pos: tuple[int, int], track: pcbnew.PCB_TRACK) -> bool:
            tolerance: int = cast(int, pcbnew.FromMM(0.25)) 
            v = pcbnew.VECTOR2I(pos[0], pos[1]) 
            return (track.IsPointOnEnds(v, tolerance) & pcbnew.STARTPOINT) != 0 # Seems to be the best option

        def pos_on_track_end(pos: tuple[int, int], track: pcbnew.PCB_TRACK) -> bool:
            tolerance: int = cast(int, pcbnew.FromMM(0.25)) 
            v = pcbnew.VECTOR2I(pos[0], pos[1]) 
            return (track.IsPointOnEnds(v, tolerance) & pcbnew.ENDPOINT) != 0 # Seems to be the best option

# --- End set of unused functions, in case needed in the future ----------------------------------------------------------

        def pos_on_either_track_endpoint(pos: tuple[int, int], track: pcbnew.PCB_TRACK) -> bool:
            return ((track.GetX() == pos[0] and track.GetY() == pos[1]) or (track.GetEndX() == pos[0] and track.GetEndY() == pos[1]))
            # Alternatives/related functions if will be required in the future for similar functionality:
            # v = pcbnew.VECTOR2I(pos[0], pos[1]) 
            # return ((track.IsPointOnEnds(v) & (pcbnew.STARTPOINT | pcbnew.ENDPOINT)) != 0) # Seems to be the best option
            # return track.HitTest(v) # Second option - this may fail if point is on the middle of track, will also return true
            # Other relevant functions in case needed in the future:
            # self.connectivity.GetConnectedItemsAtAnchor, # doesn't work - kicad bug
            # self.connectivity.TestTrackEndpointDangling
            # self.connectivity.TestTrackEndpointDangling


        def get_starter_tracks() -> dict[str, pcbnew.PCB_TRACK]:
            # Starter tracks are:
            # 1. Tracks that aren't connected on at least one endpoint to neither track nor via
            # 2. Vias that are connected to one track
            # Note: Vias that are not connected will be handled as leftovers at the end, not considered starter tracks
            starter_tracks: dict[str, pcbnew.PCB_TRACK] = {}
            track: pcbnew.PCB_TRACK
            for track in tracks_by_uuid.values():
                log_track(track, 'Checking ')
                # Must not do tolerance check, because for purpose of placing routes, if no exact match
                # of position, need to start a new route (or use 'x' command)
                if not pos_is_connected_to_track_or_via((track.GetX(), track.GetY())) or not pos_is_connected_to_track_or_via((track.GetEndX(), track.GetEndY())):  # noqa: E501
                    logger.debug('   this track is not connected to neither track/via on at least one end')
                    starter_tracks[track.m_Uuid.AsString()] = track
            via: pcbnew.PCB_VIA
            for via in vias_by_uuid.values():
                log_track(via, 'Checking ')
                if pos_is_connected_to_single_track((via.GetX(), via.GetY())):
                    logger.debug('   this via is connected to just one track')
                    starter_tracks[via.m_Uuid.AsString()] = via
            return starter_tracks


        def process_track(track: Union[pcbnew.PCB_TRACK, None],
                          try_to_start_from: Union[tuple[int, int], None] = None,
                          shallow = False):

            def start_new_route():
                nonlocal started_new_route
                nonlocal curr_net_name, curr_pos, curr_route, curr_layer, curr_pos
                if started_new_route:
                    return
                if curr_route != "":
                    logger.debug(f'Completed a route: {curr_route}')
                    routes.append(f'"{curr_route}"{"" if place_nets or curr_net_name is None or curr_net_name == "" else ("  # net: " + str(get_mapped_net(curr_net_name)))}')
                    curr_route = ""
                logger.debug("------------------------------------------ Starting new route ----------------------------------------------------------------")
                curr_net_name = None
                curr_pos = None
                curr_layer = None
                started_new_route = True

            def route_set_pos_cmd(pos: tuple[int, int]):
                nonlocal curr_route
                nonlocal curr_pos
                adjusted_x = decimal.Decimal(pos[0] - ref_x) / 1000000
                adjusted_y = decimal.Decimal(pos[1] - ref_y) / 1000000

                if orientation != 0:
                    cos = decimal.Decimal(math.cos(orientation/180.0*math.pi))
                    sin = decimal.Decimal(math.sin(orientation/180.0*math.pi))
                    oriented_x = adjusted_x*cos - adjusted_y*sin
                    oriented_y = adjusted_x*sin + adjusted_y*cos
                    adjusted_x = oriented_x
                    adjusted_y = oriented_y

                adjusted_x = round(adjusted_x, 5).normalize()
                adjusted_y = round(adjusted_y,5).normalize()

                logger.debug(f'Adding position ({str(adjusted_x)},{str(adjusted_y)})')
                curr_route += f'({(adjusted_x)},{(adjusted_y)})'
                curr_pos = pos

            def route_set_layer_cmd(layer: str):
                assert layer == 'F' or layer == 'B', f'Layer can be either B or F and received "{str}" instead'
                nonlocal curr_route
                nonlocal curr_layer
                logger.debug(f'Switching layer {curr_layer} -> {layer}')
                curr_route += layer
                curr_layer = layer

            def get_mapped_net(net_name:str) -> Union[str, None]:
                if net_name in nets_map.keys():
                    net_name = nets_map[net_name]
                return net_name

            def route_set_net_cmd(net_name: str):
                nonlocal curr_route
                nonlocal curr_net_name
                net_name_cmd = get_mapped_net(net_name)
                logger.debug(f'Switching Net {curr_net_name}->{net_name}')
                if net_name != '' and place_nets:
                    curr_route += f'<!{net_name_cmd}>'
                curr_net_name = net_name

            def route_place_via_cmd():
                nonlocal curr_route
                nonlocal curr_layer
                curr_route += 'V'
                if curr_layer == 'F':
                    curr_layer = 'B'
                elif curr_layer == 'B':
                    curr_layer = 'F'

            # process_track(..) implementation

            nonlocal curr_net_name
            nonlocal curr_route
            nonlocal curr_pos
            nonlocal curr_layer
            started_new_route = False

            # This is used to flush the current route into the routes list
            if track is None:
                start_new_route()
                return []

            # First verify this track or via are/were not already in-process/processed
            # Note that once we set them as processed as we enter, not waiting for processing completion
            track_uuid = track.m_Uuid.AsString()
            if track_uuid not in tracks_by_uuid and track_uuid not in vias_by_uuid:
                return
            if track_uuid in processed_tracks or track_uuid in processed_vias:
                return

            track_type = track.GetTypeDesc()

            # Processing of Via type
            if track_type == 'Via':
                via = track  # rename for clarity
                # Mark as processed immediately, in case mid processing we recurse
                processed_vias[track_uuid] = via

                log_track(track, "Processing ")
                via_pos = (via.GetX(), via.GetY())
                via_net_name = via.GetNetname()

                if via_net_name != curr_net_name:
                    logger.debug(f'Starting new route because via net name {via_net_name} != curr_net_name {curr_net_name}')
                    start_new_route()
                    route_set_net_cmd(via_net_name)
                if via_pos != curr_pos: # Here should be an accurate test, not approximate since it is about placing position command
                    logger.debug(f'Starting new route because via position {via_pos} != curr_net_name {curr_pos}')
                    start_new_route()
                    route_set_pos_cmd(via_pos)

                route_place_via_cmd()

                via_connected_tracks = self.connectivity.GetConnectedTracks(via)
                logger.debug(f'Via is conntected to {via_connected_tracks.size()} tracks')
                via_connected_track: pcbnew.PCB_TRACK
                if not shallow:
                    start_from_layer: str
                    if curr_layer is None:
                        start_from_layer = "F"
                    else:
                        start_from_layer = curr_layer
                    start_from_layer += ".Cu"
                    # Do first outgoing routes that match current layer
                    for via_connected_track in via_connected_tracks:
                        if via_connected_track.GetLayerName() == start_from_layer:
                            log_track(via_connected_track, "Via processing of ")
                            process_track(via_connected_track, via_pos)
                            log_track(via_connected_track, "Via processing completed of ")
                    for via_connected_track in via_connected_tracks:
                        if via_connected_track.GetLayerName() != start_from_layer:
                            log_track(via_connected_track, "Via processing of ")
                            process_track(via_connected_track, via_pos)
                            log_track(via_connected_track, "Via processing completed of ")

                return # Done handling the via case
            
            # Start handling the Track case

            assert track_type == 'Track', f'PCB(Track) Items of type {track_type} are not supported'

            processed_tracks[track_uuid] = track # mark it already as processed in case of recursion through via

            log_track(track, "Processing ")

            connected_tracks = self.connectivity.GetConnectedTracks(track)
            for connected_track in connected_tracks:
                log_track(connected_track, "  -> ")

            track_net_name: str = track.GetNetname()
            # track start/end are two points in KiCad terms, it doesn't reflect
            # on which is going to be the start or end for track points placement
            track_start_pos = (track.GetX(), track.GetY())
            track_end_pos = (track.GetEndX(), track.GetEndY())
            track_layer: str = track.GetLayerName()[0]

            # First we perform tests to see if a new route needs to start
            # Only later we fill in the route, that's important

            # If net changes we start a new route, this is easier to follow in the routes, we could have also just switched nets
            # Could just 'or' the tests, but for loggig purpose separating them
            if track_net_name != curr_net_name:
                logger.debug(f'starting new route because of net name {track_net_name} != {curr_net_name}')
                start_new_route()

            # If we need to jump position we start a new route, again, it is easier to follow, we could have used the X command to jump
            # This needs to be accurate test because it drives position placement
            if track_start_pos != curr_pos and track_end_pos != curr_pos: 
                logger.debug(f'starting new route because of position - {curr_pos} != {track_start_pos}, {track_end_pos}')
                start_new_route()

            # End of tests for starting new routes

            # Start by handling the case where track isn't connected to curr_pos so need to start a new route
            # This needs to be accurate test because it drives position placement
            if started_new_route:
                logger.debug('Track endpoints dont match curr_pos, so need to pick starting end')
                # This is a new route (which was started above) due to no match in position from curr_pos to neither ends of the track 
                # It may be touching a previuos track but not exact coordinates so we are forced to start a new route
                # Will have to pick a starting position,
                
                selected_start_pos: Union[tuple[int, int], None] = None
                # First priority - try to start new route from the point asked by calling track
                if track_start_pos == try_to_start_from:
                    logger.debug('Picked starting end based on try_to_start_from(1)')
                    selected_start_pos = track_start_pos
                elif track_end_pos == try_to_start_from:
                    logger.debug('Picked starting end based on try_to_start_from(2)')
                    selected_start_pos = track_end_pos
                # Second priority - try to start new route from a dangling endpoint (so not connected to another track, ignoring vias)
                elif pos_is_connected_to_track(track_start_pos) and not pos_is_connected_to_track(track_end_pos):
                    logger.debug('Picked starting end based on dangling end')
                    selected_start_pos = track_end_pos
                elif pos_is_connected_to_track(track_end_pos) and not pos_is_connected_to_track(track_start_pos):
                    logger.debug('Picked starting end based on dangling start')
                    selected_start_pos = track_start_pos
                else: 
                    # could pick arbitrarily, but let's put some logic to make routes organized nicer
                    # if there is try_to_start_from pick the closest to try_to_start_from
                    if try_to_start_from is not None:
                        if distance(track_start_pos, try_to_start_from) < distance(track_end_pos, try_to_start_from):
                            selected_start_pos = track_start_pos
                        else:
                            selected_start_pos = track_end_pos

                # If after all above couldn't decide, pick arbitrarily
                if selected_start_pos is None:
                    logger.debug("  Picked starting end at startpoint arbitrarily because no other reasoned choice met")
                    selected_start_pos = track_start_pos

                # if the track start point has a via, then place it first, but not its connected tracks (see below)
                connected_tracks = self.connectivity.GetConnectedTracks(track)
                connected_track: pcbnew.PCB_TRACK
                for connected_track in connected_tracks:
                    track_type = connected_track.GetTypeDesc()
                    if track_type == 'Via':
                        via_pos = (connected_track.GetX(), connected_track.GetY())
                        if via_pos == selected_start_pos:
                            # processing via SHALLOW (only the via and not connected tracks),
                            # otherwise, in case of loop might process this track after curr_pos 
                            # changed and selected_start_pos sohuld be different after selected (so need to reselect)
                            # Cant allow curr_pos to change now
                            process_track(connected_track, shallow=True)

                # Now place route net, layer and start position
                
                if track_net_name != curr_net_name:
                    route_set_net_cmd(track_net_name)

                if track_layer != curr_layer:
                    route_set_layer_cmd(track_layer)

                if selected_start_pos != curr_pos:
                    route_set_pos_cmd(selected_start_pos)

                # End of handling the curr_pos not match track case

            # the following net and layer, not sure if needed, but won't hurt for now
            if track_net_name != curr_net_name:
                route_set_net_cmd(track_net_name)

            if track_layer != curr_layer:
                route_set_layer_cmd(track_layer)

            # Now complete the second endpoint of the track (the one that isn't cur_pos), need an accurate check, no tolerances
            if track_start_pos == curr_pos:
                route_set_pos_cmd(track_end_pos)
            elif track_end_pos == curr_pos:
                route_set_pos_cmd(track_start_pos)
            else:
                assert True, "At this point one of the ends should have been curr_pos"

            # Process connected tracks and vias, with an order that would yield nicest/shortest route
            connected_tracks = self.connectivity.GetConnectedTracks(track)
            connected_track: pcbnew.PCB_TRACK

            assert curr_pos is not None, "At this point curr_pos must have a value, otherwise it means alrogirhm blundered"

            track_finish_pos: tuple[int, int] = cast(tuple[int, int], curr_pos) # record track end position before recursion

            # Processing next, in the following order:
            # 1. vias that are connected on this end of the track 
            # 2. real' tracks that are connected on this end of the track
            # 3. connected tracks through Pads on this end of the track
            # This order for for shorter routes in some cases (when via is not connected on other layer)
 
            for connected_track in connected_tracks:
                track_type = connected_track.GetTypeDesc()
                if track_type == 'Via' and track_finish_pos and pos_on_either_track_endpoint(track_finish_pos, connected_track):
                    logger.debug("Calling process_track with via")
                    process_track(connected_track, track_finish_pos)

            for connected_track in connected_tracks:
                track_type = connected_track.GetTypeDesc()
                if track_type == 'Track' and track_finish_pos and pos_on_either_track_endpoint(track_finish_pos, connected_track):
                    process_track(connected_track, track_finish_pos)

            # Now process connected tracks/vias that we can connect to through pad, only if they are all on the exact position
            connected_pads = self.connectivity.GetConnectedPads(track)
            connected_pad: pcbnew.PAD
            for connected_pad in connected_pads:
                if track_finish_pos and connected_pad.GetX() == track_finish_pos[0] and connected_pad.GetY() == track_finish_pos[1]:
                    pad_connected_tracks = self.connectivity.GetConnectedTracks(connected_pad)
                    pad_connected_track: pcbnew.PCB_TRACK
                    for pad_connected_track in pad_connected_tracks:
                        track_type = pad_connected_track.GetTypeDesc()
                        if track_type == 'Via' and track_finish_pos and pos_on_either_track_endpoint(track_finish_pos, pad_connected_track):
                            logger.debug("Processing track connected through Pad")
                            process_track(pad_connected_track, track_finish_pos)

                    for pad_connected_track in pad_connected_tracks:
                        track_type = pad_connected_track.GetTypeDesc()
                        if track_type == 'Track' and track_finish_pos and pos_on_either_track_endpoint(track_finish_pos, pad_connected_track):
                            process_track(pad_connected_track, track_finish_pos)


        #### process_tracks(...) implementation

        # first let's address those tracks that start a route. to find them,
        # need to find those tracks that aren't connected on at least one end to anything
        # or vias that are connected to only a single track
        # BUT not connected means to other tracks on the list,
        # could be in the PCB they are connected but we don't want those
        # parts to be considred
        # AND connection means exact connection, could be on the PCB they are touching
        # but for routing purpose, because coordinates are different they are not considered 
        # connected

        tracks_by_pos: dict[tuple[int, int], list[pcbnew.PCB_TRACK]]
        vias_by_pos: dict[tuple[int, int], list[pcbnew.PCB_VIA]]
        tracks_by_pos, vias_by_pos = get_tracks_by_pos()
        logger.debug("=======> Searching for Starter Tracks/Vias <=======")
        starter_tracks: dict[str, pcbnew.PCB_TRACK] = get_starter_tracks()

        processed_tracks: dict[str, pcbnew.PCB_TRACK] = {}
        processed_vias: dict[str, pcbnew.PCB_TRACK] = {}
        curr_route: str = ""
        curr_pos: Union[tuple[int, int], None] = None
        curr_layer: Union[str, None] = None
        curr_net_name: Union[str, None] = None
        routes: list[str] = []

        logger.debug(f'=======> Found {len(starter_tracks)} Starting tracks <=======')
        for track in starter_tracks.values():
            log_track(track)

        logger.debug("=======> Processing Starter Tracks <=======")
        for track in starter_tracks.values():
            logger.debug("=> Starting processing of a Starter Track")
            process_track(track)

        # later need to cover all those routes that don't have a starting
        # point, like loops. For that easiest would be to iterate through
        # the complete list of tracks, all those that were already processed
        # will be ignored
        logger.debug("=======> Processing Loops of Tracks <=======")
        for track in tracks_by_uuid.values():
            process_track(track)

        # Proceccing dangling vias that weren't processed because aren't reached through tracks
        logger.debug("=======> Processing Dangling Vias Last <=======")
        for via in vias_by_uuid.values():
            if via.m_Uuid.AsString() not in processed_vias:
                process_track(via)

        # "Flush" last route and add it to the list of routes with all processing
        if curr_route != "":
            process_track(None)

        return routes
