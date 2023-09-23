from typing import Union
import pcbnew
from collections import defaultdict
import decimal
import math
from .helper import get_logger
logger = get_logger(__name__)


def log_track(track: pcbnew.PCB_TRACK, prefix=""):
    logger.debug(f'{prefix}track NC:{track.GetNetCode()},NN:{track.GetNetname()},({pcbnew.ToMM(track.GetX())},{pcbnew.ToMM(track.GetY())})->({pcbnew.ToMM(track.GetEndX())},{pcbnew.ToMM(track.GetEndY())}), {track.m_Uuid.AsString()}')  # noqa: E501


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
        logger.debug(str(sel_analysis.nets))
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
                logger.debug('Found track')
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
        yaml += 2 * tab_size * " " + f'where: {filter} # change filter as needed\n'
        yaml += 2 * tab_size * " " + "params:\n"
        yaml += 3 * tab_size * " " + "routes:\n"
        for route in routes:
            yaml += 4 * tab_size * " " + '- ' + route + '\n'
        return yaml


    def get_selection_router_config(self, ref_fp_name: str, nets_map: dict[str, str], footprint_tracks: bool, selected_tracks_vias: bool,
                                    include_locked_tracks_vias:bool, 
                                    place_nets:bool = True, tab_size: int = 2, fp_sec_name:str= "", where_filter:str = "true") -> str:
        logger.debug(f'get_selection_router_config with {footprint_tracks}, {selected_tracks_vias}')
        selected_items = pcbnew.GetCurrentSelection()
        footprints: list[pcbnew.FOOTPRINT] = []
        ref_fp: Union[pcbnew.FOOTPRINT, None] = None
        all_tracks: dict[str, pcbnew.PCB_TRACK] = {}
        all_vias: dict[str, pcbnew.PCB_VIA] = {}

        for item in selected_items:
            if item.GetTypeDesc() == 'Footprint':
                logger.debug(f'Footprint Selected: {item.GetReferenceAsString()}')
                footprints.append(item.Cast())
                if item.GetReferenceAsString() == ref_fp_name:
                    ref_fp = item

        if len(footprints) == 0:
            return 'No footprints in selection, at least one needed for reference position'

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

        logger.debug(f'Found total tracks: {len(all_tracks)} and vias: {len(all_vias)}')
        if ref_fp is not None:
            routes = self.process_tracks(all_tracks, all_vias, ref_fp.GetX(), ref_fp.GetY(),
                                         ref_fp.GetOrientationDegrees(), place_nets, nets_map)
            return self.get_routes_yaml(routes, tab_size, fp_sec_name, where_filter)
        else:
            return 'No response'

##################################################################

    def get_footprints_tracks(self, footprints: list[pcbnew.FOOTPRINT]) -> tuple[dict[str, pcbnew.PCB_TRACK], dict[str, pcbnew.PCB_VIA]]:

        def add_connected_tracks(item: pcbnew.BOARD_CONNECTED_ITEM):
            nonlocal tracks_by_uuid
            nonlocal vias_by_uuid
            connected_tracks = self.connectivity.GetConnectedTracks(item)
            track: pcbnew.PCB_TRACK
            for track in connected_tracks:
                track_uuid = track.m_Uuid.AsString()
                if track_uuid in tracks_by_uuid or track_uuid in vias_by_uuid:
                    # logger.debug("Track already encountered")
                    continue
                if track.GetTypeDesc() == 'Track':
                    tracks_by_uuid[track_uuid] = track
                elif track.GetTypeDesc() == 'Via':
                    vias_by_uuid[track_uuid] = track.Cast()
                add_connected_tracks(track)

        tracks_by_uuid: dict[str, pcbnew.PCB_TRACK] = {}
        vias_by_uuid: dict[str, pcbnew.PCB_VIA] = {}
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

        def get_tracks_by_pos() -> dict[tuple[int, int], list[pcbnew.PCB_TRACK]]:
            tracks_by_pos: dict[tuple[int, int], list[pcbnew.PCB_TRACK]] = defaultdict(list)  # noqa: E501
            for track in tracks_by_uuid.values():
                tracks_by_pos[(track.GetX(), track.GetY())].append(track)
                tracks_by_pos[(track.GetEndX(), track.GetEndY())].append(track)
            return tracks_by_pos

        def end_is_connected(x: int, y: int) -> bool:
            # currently doing exact match, but maybe need some tolerance, see pos_on_track_end for functions to use
            return len(tracks_by_pos[(x, y)]) > 1

        def pos_on_track_end(pos: tuple[int, int], track: pcbnew.PCB_TRACK):
            # First option for this test, but does only exact match w/o any tolerance
            # return ((track.GetX() == pos[0] and track.GetY() == pos[1]) or (track.GetEndX() == pos[0] and track.GetEndY() == pos[1]))
            v = pcbnew.VECTOR2I(pos[0], pos[1]) 
            # return track.HitTest(v) # Second option - this may fail if point is on the middle of track, will also return true
            return ((track.IsPointOnEnds(v) & (pcbnew.STARTPOINT | pcbnew.ENDPOINT)) != 0) # Seems to be the best option
            # Other relevant functions in case needed in the future:
            # self.connectivity.GetConnectedItemsAtAnchor, # doesn't work - kicad bug
            # self.connectivity.TestTrackEndpointDangling
            # self.connectivity.TestTrackEndpointDangling

        def get_starter_tracks() -> dict[str, pcbnew.PCB_TRACK]:

            starter_tracks: dict[str, pcbnew.PCB_TRACK] = {}
            track: pcbnew.PCB_TRACK
            for track in tracks_by_uuid.values():
                logger.debug(f'{track.m_Uuid.AsString()}')
                if not end_is_connected(track.GetX(), track.GetY()) or not end_is_connected(track.GetEndX(), track.GetEndY()):  # noqa: E501
                    logger.debug('   this one is not connected on one end at least one end')
                    starter_tracks[track.m_Uuid.AsString()] = track
            return starter_tracks


        def process_track(track: Union[pcbnew.PCB_TRACK, None], try_to_start_from: Union[tuple[int, int], None] = None): # -> Union[list[str], None]:

            def start_new_route():
                nonlocal started_new_route
                nonlocal curr_net_name, curr_pos, curr_route, curr_layer, curr_pos
                if started_new_route:
                    return
                if curr_route != "":
                    logger.debug(f'Completed a route: {curr_route}')
                    routes.append(f'"{curr_route}"{"" if place_nets or curr_net_name is None else ("  # net: " + str(get_mapped_net(curr_net_name)))}')
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
                    adjusted_x = round(oriented_x, 5).normalize()
                    adjusted_y = round(oriented_y,5).normalize()

                logger.debug(f'Adding position {(adjusted_x),(adjusted_y)}')
                curr_route += f'({(adjusted_x)},{(adjusted_y)})'
                curr_pos = pos

            def route_set_layer_cmd(layer: str):
                assert layer == 'F' or layer == 'B', f'Layer can be either B or F and received "{str}" instead'
                nonlocal curr_route
                nonlocal curr_layer
                logger.debug("Switching layer")
                curr_route += layer
                curr_layer = layer

            def get_mapped_net(net_name:str) -> Union[str, None]:
                if net_name in nets_map.keys():
                    net_name = nets_map[net_name]
                return net_name

            def route_set_net_cmd(net_name: str):
                nonlocal curr_route
                nonlocal curr_net_name
                logger.debug(str(nets_map))
                # net_name_cmd = net_name
                # if net_name in nets_map.keys():
                #     net_name_cmd = nets_map[net_name]
                net_name_cmd = get_mapped_net(net_name)
                logger.debug(f'Creating new Net {curr_net_name}->{net_name}')
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
                processed_vias[via.m_Uuid.AsString()] = via

                log_track(track, "Processing Via: ")
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
                for via_connected_track in via_connected_tracks:
                    log_track(via_connected_track, "Via processing ")
                    process_track(via_connected_track, via_pos)

                return # Done handling the via case
            
            # Start handling the Track case

            assert track_type == 'Track', f'PCB(Track) Items of type {track_type} are not supported'

            processed_tracks[track_uuid] = track # mark it already as processed in case of recursion through via

            log_track(track, "Processing Track: ")

            connected_tracks = self.connectivity.GetConnectedTracks(track)
            for connected_track in connected_tracks:
                log_track(connected_track, "  -> ")

            track_net_name: str = track.GetNetname()
            track_end1 = (track.GetX(), track.GetY())
            track_end2 = (track.GetEndX(), track.GetEndY())
            track_layer: str = track.GetLayerName()[0]

            # First we perform tests to see if a new route will need to start
            # Only later we fill in the route, that's important

            # If net changes we start a new route, this is easier to follow in the routes, we could have also just switched nets
            # Could just 'or' the tests, but for loggig purpose separating them
            if track_net_name != curr_net_name:
                logger.debug(f'starting new route because of net name {track_net_name} != {curr_net_name}')
                start_new_route()

            # If we need to jump position we start a new route, again, it is easier to follow, we could have used the X command to jump
            # TODO: compare with tolerance instead of exact match
            if track_end1 != curr_pos and track_end2 != curr_pos:
                logger.debug(f'starting new route because of position - {curr_pos} != {track_end1}, {track_end2}')
                start_new_route()

            # End of tests for starting new routes

            # TODO: compare with tolerance instead of exact match
            if track_end1 != curr_pos and track_end2 != curr_pos:
                # TODO: the test done here should not be done but rather use some temp variable from previous test which is the same
                
                # This is a new route (which was started above) due to no match in position from curr_pos to neither ends of the track 
                # Will have to provide a starting position,
                # BUT before that handle vias on the beginning of the track if available. Beginning is considering the try_to_start_from,
                # which is the point at which track that lead here in the recursion ended and from which we start
                # So need to place only vias if are on the try_to_start_from point or if try_to_start_from is None
                
                # if the track start point has a via, then place it first
                connected_tracks = self.connectivity.GetConnectedTracks(track)
                connected_track: pcbnew.PCB_TRACK
                for connected_track in connected_tracks:
                    track_type = connected_track.GetTypeDesc()
                    if track_type == 'Via':
                        if try_to_start_from is None or (try_to_start_from and pos_on_track_end(try_to_start_from, connected_track)):  # noqa: E501
                            logger.debug("Calling process_track with via at the start of a track")
                            process_track(connected_track)

            # TODO: use some variable from comparison done above
            if track_net_name != curr_net_name:
                route_set_net_cmd(track_net_name)

            if track_layer != curr_layer:
                route_set_layer_cmd(track_layer)

            # TODO: compare with tolerance instead of exact match
            # TODO: Can't Reuse tests above using some temp variable because via placement may have changed curr position, or not placed and it didn't change so need to test again
            # If track ends don't match curr_position yet (either it matched initially, or at start may have set curr pos to match)
            # We want to place the track in a continuous flow from the end of the track that triggered it as its connected track if that's the scenario
            # So checking the options of which end to start from
            if track_end1 != curr_pos and track_end2 != curr_pos:
                logger.debug(f'Track that begins a route: end1: {track_end1} end2: {track_end2}: try_to_start_from: {try_to_start_from}, curr_pos: {curr_pos}')
                # Start by continuous flow from calling track
                # if not, then try to start from an end that isn't connected to anything (in case it is a starter track)
                # TODO: compare with tolerance instead of exact match
                if track_end1 == try_to_start_from:
                    route_set_pos_cmd(track_end1)
                elif track_end2 == try_to_start_from:
                    route_set_pos_cmd(track_end2)
                # TODO: compare with tolerance instead of exact match - change end_is_connected to achieve that
                elif not end_is_connected(track_end1[0], track_end1[1]):
                    route_set_pos_cmd(track_end1)
                else:
                    route_set_pos_cmd(track_end2)

            # TODO: compare with tolerance instead of exact match - not sure needed, because here it's the track against its own positions
            # Now complete the second end of the track
            if track_end1 == curr_pos:
                route_set_pos_cmd(track_end2)
            elif track_end2 == curr_pos:
                route_set_pos_cmd(track_end1)
            else:
                assert True, "At this point one of the ends should have been curr_pos"

            # Process connected tracks and vias, with an order that would yield nicest/shortest route
            connected_tracks = self.connectivity.GetConnectedTracks(track)
            connected_track: pcbnew.PCB_TRACK

            # TODO: verify that track_end_pos is not None (even add assert) - this is critical to the code that comes later and assumes curr_pos can't be None
            # Even add code that changes the type to not support None and fail here if it is None
            track_end_pos = curr_pos # record track end position before recursion

            # Processing:
            # 1. all connected 'vias' 
            # 2. real' tracks 
            # 3. connected tracks through Pads
            # This order for for shorter routes in some cases (when via is not connected on other layer)
            # TODO: think if pads last is appropriate. Also think about pads that are/aren't passthrough holes (since they are like vias a bit, but not exactly)
            for connected_track in connected_tracks:
                track_type = connected_track.GetTypeDesc()
                if track_type == 'Via':
                    #  TODO: Do same as in track(see below), only vias that at on the end of the track, not the beginning
                    logger.debug("Calling process_track with via")
                    process_track(connected_track, track_end_pos)

            for connected_track in connected_tracks:
                track_type = connected_track.GetTypeDesc()
                if track_type == 'Track' and track_end_pos and pos_on_track_end(track_end_pos, connected_track):
                    process_track(connected_track, track_end_pos)

            connected_pads = self.connectivity.GetConnectedPads(track)
            connected_pad: pcbnew.PAD
            for connected_pad in connected_pads:
                # TODO: test with tolerance
                if track_end_pos and connected_pad.GetX() == track_end_pos[0] and connected_pad.GetY() ==track_end_pos[1]:
                    pad_connected_tracks = self.connectivity.GetConnectedTracks(connected_pad)
                    pad_connected_track: pcbnew.PCB_TRACK
                    for pad_connected_track in pad_connected_tracks:
                        process_track(pad_connected_track, track_end_pos)



        # process_tracks(...) implementation

        # first let's address those tracks that start a route. to find them,
        # need to find those tracks that aren't connected on at least one end
        # BUT not connected means to other tracks on the list,
        # could be in the PCB they are connected but we don't want those
        # parts to be considred
        #
        tracks_by_pos: dict[tuple[int, int], list[pcbnew.PCB_TRACK]] = get_tracks_by_pos()
        logger.debug("--> Starter Tracks")
        starter_tracks: dict[str, pcbnew.PCB_TRACK] = get_starter_tracks()

        processed_tracks: dict[str, pcbnew.PCB_TRACK] = {}
        processed_vias: dict[str, pcbnew.PCB_TRACK] = {}
        curr_route: str = ""
        curr_pos: Union[tuple[int, int], None] = None
        curr_layer: Union[str, None] = None
        curr_net_name: Union[str, None] = None
        routes: list[str] = []

        logger.debug(f'Finding Starting tracks# {len(starter_tracks)}')
        for track in starter_tracks.values():
            log_track(track)

        logger.debug("=======> Processing Starter Tracks <=======")
        for track in starter_tracks.values():
            logger.debug("*** New Starter ***")
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

        logger.info(str(routes))

        return routes
