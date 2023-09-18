from typing import Union
import pcbnew
import wx
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
                                    place_nets:bool = True, tab_size: int = 2, fp_sec_name:str= "", filter:str = "true") -> str:
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

        logger.debug(f'Found total tracks: {len(all_tracks)} and vias: {len(all_vias)}')
        if ref_fp is not None:
            routes = self.process_tracks(all_tracks, all_vias, ref_fp.GetX(), ref_fp.GetY(),
                                         ref_fp.GetOrientationDegrees(), place_nets, nets_map)
            return self.get_routes_yaml(routes, tab_size, fp_sec_name, filter)
        else:
            return 'No response'

    def get_selected_router_config(self) -> Union[list[str], None]:
        selected_items = pcbnew.GetCurrentSelection()
        footprints: list[pcbnew.FOOTPRINT] = []
        largest_area = 0
        largest_footprint: Union[pcbnew.FOOTPRINT, None] = None
        for item in selected_items:
            if item.GetTypeDesc() == 'Footprint':
                logger.debug(f'Footprint Selected: {item.GetReferenceAsString()}')
                footprints.append(item.Cast())
                if item.GetArea() > largest_area:
                    largest_area = item.GetArea()
                    largest_footprint = item
        if len(footprints) == 0:
            wx.MessageBox("No footprints in selection")
            return

        all_tracks, all_vias = self.get_footprints_tracks(footprints)
        logger.debug(f'Found total tracks: {len(all_tracks)} and vias: {len(all_vias)}')
        if largest_footprint:
            return self.process_tracks(all_tracks, all_vias, largest_footprint.GetX(), largest_footprint.GetY(),
                                       largest_footprint.GetOrientationDegrees())

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
            # currently doing exact match, but maybe need some tolerance
            return len(tracks_by_pos[(x, y)]) > 1

        def get_starter_tracks() -> dict[str, pcbnew.PCB_TRACK]:

            starter_tracks: dict[str, pcbnew.PCB_TRACK] = {}
            track: pcbnew.PCB_TRACK
            for track in tracks_by_uuid.values():
                logger.debug(f'{track.m_Uuid.AsString()}')
                if not end_is_connected(track.GetX(), track.GetY()) or not end_is_connected(track.GetEndX(), track.GetEndY()):  # noqa: E501
                    logger.debug('   this one is not connected on one end at least one end')
                    starter_tracks[track.m_Uuid.AsString()] = track
            return starter_tracks


        def process_track(track: Union[pcbnew.PCB_TRACK, None]): # -> Union[list[str], None]:

            def start_new_route():
                nonlocal started_new_route
                nonlocal curr_net_name, curr_pos, curr_route, curr_layer, curr_pos
                logger.debug("Starting new route")
                if started_new_route:
                    return
                if curr_route != "":
                    logger.debug(curr_route)
                    routes.append(f'"{curr_route}"{"" if place_nets or curr_net_name is None else ("  # net: " + curr_net_name)}')
                    curr_route = ""
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

            def route_set_net_cmd(net_name: str):
                nonlocal curr_route
                nonlocal curr_net_name
                logger.debug(str(nets_map))
                net_name_cmd = net_name
                if net_name in nets_map.keys():
                    net_name_cmd = nets_map[net_name]
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
                if curr_layer == 'B':
                    curr_layer = 'F'

            # process_track(..) implementation

            nonlocal curr_net_name
            nonlocal curr_route
            nonlocal curr_pos
            nonlocal curr_layer
            started_new_route = False

            if track is None:
                start_new_route()
                return []

            track_uuid = track.m_Uuid.AsString()
            if track_uuid not in tracks_by_uuid and track_uuid not in vias_by_uuid:
                return
            if track_uuid in processed_tracks or track_uuid in processed_vias:
                return

            track_type = track.GetTypeDesc()
            if track_type == 'Via':
                via = track  # rename for clarity
                logger.debug("Processing via")
                via_pos = (via.GetX(), via.GetY())
                via_net_name = via.GetNetname()
                if via_net_name != curr_net_name:
                    start_new_route()
                    route_set_net_cmd(via_net_name)
                if via_pos != curr_pos:
                    start_new_route()
                    route_set_pos_cmd(via_pos)
                route_place_via_cmd()
                processed_vias[via.m_Uuid.AsString()] = via

                via_connected_tracks = self.connectivity.GetConnectedTracks(via)
                logger.debug(f'Via is conntected to {via_connected_tracks.size()} tracks')
                via_connected_track: pcbnew.PCB_TRACK
                for via_connected_track in via_connected_tracks:
                    log_track(via_connected_track, "Via processing ")
                    process_track(via_connected_track)

                return

            assert track_type == 'Track', f'PCB(Track) Items of type {track_type} are not supported'

            log_track(track, "Processing Track! ")
            connected_tracks = self.connectivity.GetConnectedTracks(track)
            for connected_track in connected_tracks:
                log_track(connected_track, "  -> ")

            track_net_name: str = track.GetNetname()
            track_end1 = (track.GetX(), track.GetY())
            track_end2 = (track.GetEndX(), track.GetEndY())

            if track_net_name != curr_net_name:
                logger.debug("starting new layer because of net change")
                start_new_route()
            if (track_end1 != curr_pos and track_end2 != curr_pos):
                logger.debug(f'starting new layer because of position - {curr_pos} != {track_end1}, {track_end2}')
                start_new_route()

            if track_net_name != curr_net_name:
                route_set_net_cmd(track_net_name)

            layer: str = track.GetLayerName()[0]
            if layer != curr_layer:
                route_set_layer_cmd(layer)

            if track_end1 != curr_pos and track_end2 != curr_pos:
                if not end_is_connected(track_end1[0], track_end1[1]):
                    route_set_pos_cmd(track_end1)
                else:
                    route_set_pos_cmd(track_end2)

            if track_end1 == curr_pos:
                route_set_pos_cmd(track_end2)
            elif track_end2 == curr_pos:
                route_set_pos_cmd(track_end1)
            else:
                assert True, "At this point one of the ends should be curr_pos"

            processed_tracks[track_uuid] = track

            connected_tracks = self.connectivity.GetConnectedTracks(track)
            connected_track: pcbnew.PCB_TRACK

            # Processing all connected 'real' tracks, and only after 'vias' for nicer routes
            for connected_track in connected_tracks:
                track_type = connected_track.GetTypeDesc()
                if track_type == 'Track':
                    process_track(connected_track)
            for connected_track in connected_tracks:
                track_type = connected_track.GetTypeDesc()
                if track_type == 'Via':
                    logger.debug("Calling process_track with via")
                    process_track(connected_track)

            connected_pads = self.connectivity.GetConnectedPads(track)
            connected_pad: pcbnew.PAD
            for connected_pad in connected_pads:
                pad_connected_tracks = self.connectivity.GetConnectedTracks(connected_pad)
                pad_connected_track: pcbnew.PCB_TRACK
                for pad_connected_track in pad_connected_tracks:
                    process_track(pad_connected_track)



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
