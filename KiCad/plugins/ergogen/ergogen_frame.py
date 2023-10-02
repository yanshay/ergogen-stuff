import wx
import random
from .router_gen import RouterGen, SelectionAnalysis


from .helper import get_logger
logger = get_logger(__name__)


INSTRUCTIONS = '''Instructions
------------
1. Select at least one footpring and optionally routes/vias
2. Press Analyze Selection
3. Fill your choices in Route Specification Selection
4. Press Generate Routes Button
5. Check results and if satisfied, copy to clipboard and paste in your ErgoGen config file
'''

class ErgogenFrame(wx.Frame):

    panel: wx.Panel

    info_footprints: wx.StaticText
    info_tracks: wx.StaticText
    info_vias: wx.StaticText
    info_nets: wx.StaticText
    info_unsupported: wx.StaticText

    collect_fp_tracks: wx.CheckBox
    include_selected_tracks: wx.CheckBox
    include_locked_tracks_vias: wx.CheckBox
    ref_fp: wx.ComboBox
    place_nets: wx.CheckBox
    nets_sz: wx.FlexGridSizer
    nets_win: wx.ScrolledWindow
    nets: dict[str, wx.ComboBox]

    tab_size: wx.SpinCtrl
    fp_sec_name: wx.TextCtrl
    filter: wx.TextCtrl

    yaml_txt: wx.TextCtrl

    def __init__(self):
        pcbnew_frame = wx.FindWindowByName("PcbFrame")
        super().__init__(pcbnew_frame)
        self.nets = {}
        self.init_ui()

    def init_ui(self):

        self.SetTitle("Ergogen Kicad Plugin")
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.SetSize(600, 900)
        self.panel = wx.Panel(self)

        self.main_sz = wx.BoxSizer(wx.VERTICAL)
        self.build_sel_analysis()
        self.build_route_spec()
        self.build_execution()

        self.panel.SetSizer(self.main_sz)

    def build_sel_analysis(self):

        sel_analysis_sz = wx.StaticBoxSizer(wx.VERTICAL, self.panel, "Selection Analysis")
        sb = sel_analysis_sz.GetStaticBox()
        analyze_btn = wx.Button(sb, wx.ID_ANY, label="Analyze Selection")
        sel_analysis_sz.Add(analyze_btn, flag=wx.EXPAND)

        info_sz = wx.FlexGridSizer(2, 5, 5)
        self.info_footprints = wx.StaticText(sb, label="?")
        self.info_tracks = wx.StaticText(sb, label="?")
        self.info_vias = wx.StaticText(sb, label="?")
        self.info_nets = wx.StaticText(sb, label="?")
        self.info_unsupported = wx.StaticText(sb, label="?")

        info_sz.AddMany([wx.StaticText(sb, label="Footprints:"), self.info_footprints,
                         wx.StaticText(sb, label="Tracks:"), self.info_tracks,
                         wx.StaticText(sb, label="Vias:"), self.info_vias,
                         wx.StaticText(sb, label="Nets:"), self.info_nets,
                         wx.StaticText(sb, label="Unsupported:"), self.info_unsupported
                         ])
        sel_analysis_sz.Add(info_sz, flag=wx.ALL, border=10)

        self.main_sz.Add(sel_analysis_sz, flag=wx.ALL | wx.EXPAND, border=10)
        # self.main_sz.Fit(self)
        analyze_btn.Bind(wx.EVT_BUTTON, self.OnAnalyze)


    def build_route_spec(self):
        route_spec_sz = wx.StaticBoxSizer(wx.VERTICAL, self.panel, "Route Specifications")
        sb = route_spec_sz.GetStaticBox()

        self.collect_fp_tracks = wx.CheckBox(sb, label="Collect tracks connected to selected footprints")
        route_spec_sz.Add(self.collect_fp_tracks, flag=wx.LEFT, border=10)
        route_spec_sz.AddSpacer(5)

        self.include_selected_tracks = wx.CheckBox(sb, label="Include seleted tracks and vias")
        route_spec_sz.Add(self.include_selected_tracks, flag=wx.LEFT, border=10)
        route_spec_sz.AddSpacer(5)

        self.include_locked_tracks_vias = wx.CheckBox(sb, label="Include locked tracks/vias")
        self.include_locked_tracks_vias.SetValue(True)
        route_spec_sz.Add(self.include_locked_tracks_vias, flag=wx.LEFT, border=10)
        route_spec_sz.AddSpacer(5)

        combo_sz = wx.BoxSizer(wx.HORIZONTAL)
        ref_fp_label = wx.StaticText(sb, label="Reference footprint")
        self.ref_fp = wx.ComboBox(sb, style=wx.CB_READONLY)
        combo_sz.AddMany([ref_fp_label, (self.ref_fp, 0, wx.EXPAND | wx.LEFT, 5)])
        route_spec_sz.Add(combo_sz, 0, flag=wx.EXPAND | wx.LEFT, border=10)
        route_spec_sz.AddSpacer(5)

        self.place_nets = wx.CheckBox(sb, label="Place network names (disable with unpatched ErgoGen at this time)")
        self.place_nets.SetValue(False)
        route_spec_sz.Add(self.place_nets, flag=wx.LEFT, border=10)
        route_spec_sz.AddSpacer(5)

        net_map_label = wx.StaticText(sb, label="Map nets:")
        route_spec_sz.Add(net_map_label, flag=wx.LEFT, border=10)
        self.nets_win = wx.ScrolledWindow(sb, style=wx.SIMPLE_BORDER, size=(100, 150))
        self.nets_sz = wx.FlexGridSizer(2, 5, 5)
        self.nets_win.SetScrollbars(1, 1, 1, 1)
        self.nets_win.SetSizer(self.nets_sz)
        route_spec_sz.Add(self.nets_win, 1, flag=wx.EXPAND | wx.LEFT, border=10)

        routes_placeholders_sz = wx.BoxSizer(wx.HORIZONTAL)
        tab_size_label = wx.StaticText(sb, label="Tab size:")
        self.tab_size = wx.SpinCtrl(sb, value='2', style=wx.TE_READONLY)
        fp_name_label = wx.StaticText(sb, label="Footprint name:")
        self.fp_sec_name = wx.TextCtrl(sb, value="routes_fp_" + str(random.randint(100,999)))
        filter_label = wx.StaticText(sb, label="Filter:")
        self.filter = wx.TextCtrl(sb, value="true")

        routes_placeholders_sz.AddMany([(tab_size_label, 0, wx.CENTER | wx.LEFT, 10), 
                                        (self.tab_size, 0, wx.LEFT, 5),
                                        (fp_name_label, 0, wx.CENTER | wx.LEFT, 10),
                                        (self.fp_sec_name, 1, wx.LEFT, 5),
                                        (filter_label, 0, wx.CENTER | wx.LEFT, 10),
                                        (self.filter, 1, wx.LEFT, 5)
                                        ])
        route_spec_sz.AddSpacer(5)
        route_spec_sz.Add(routes_placeholders_sz, 0, wx.EXPAND, border=10)

        self.main_sz.Add(route_spec_sz, 0, flag=wx.ALL | wx.EXPAND, border=10)

    def clear_nets(self):
        for w in self.nets_sz.GetChildren():
            w.GetWindow().Destroy()
        self.nets.clear()

    def set_nets(self, nets_list: set[str]):
        self.clear_nets()
        for net in nets_list:
            st = wx.StaticText(self.nets_win, label=f'"{net}" : ', style=wx.ALIGN_RIGHT)
            cb = wx.ComboBox(self.nets_win, value=net, choices=[net, '{{colrow}}', '{{column_net}}', '{{row_net}}'])
            self.nets_sz.Add(st, flag=wx.EXPAND | wx.CENTER | wx.TOP, border=3)
            self.nets_sz.Add(cb)
            self.nets[net] = cb
        self.nets_win.Layout()
        self.nets_win.FitInside()

    def get_nets_map(self) -> dict[str, str]:
        nets_map: dict[str, str] = {}
        for key in self.nets.keys():
            nets_map[key] = self.nets[key].GetValue()
        return nets_map


    def build_execution(self):
        execution_sz = wx.StaticBoxSizer(wx.VERTICAL, self.panel, "Execution")
        sb = execution_sz.GetStaticBox()
        exec_btn = wx.Button(sb, label="Generate Routes")
        execution_sz.Add(exec_btn, flag=wx.EXPAND)
        exec_btn.Bind(wx.EVT_BUTTON, self.OnGenRoute)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        yaml_lbl = wx.StaticText(sb, label="Yaml routes:")
        hsizer.Add(yaml_lbl, flag=wx.TOP, border=5)
        hsizer.AddStretchSpacer(1)
        clear_btn = wx.Button(sb, label="Clear")
        hsizer.Add(clear_btn, flag=wx.TOP, border=5)
        clear_btn.Bind(wx.EVT_BUTTON, self.OnClearYaml)
        copy_btn = wx.Button(sb, label="Copy to Clipboard")
        hsizer.Add(copy_btn, flag=wx.TOP | wx.LEFT, border=5)
        copy_btn.Bind(wx.EVT_BUTTON, self.OnCopyToClipboard)
        execution_sz.Add(hsizer, flag=wx.TOP | wx.EXPAND, border=5)
        font: wx.Font = self.GetFont()
        font.SetFamily(wx.FONTFAMILY_TELETYPE)
        self.yaml_txt = wx.TextCtrl(sb, value=INSTRUCTIONS, style=wx.TE_MULTILINE)
        self.yaml_txt.OSXDisableAllSmartSubstitutions()
        self.yaml_txt.SetSizeHints(0, 800)
        self.yaml_txt.SetFont(font)
        execution_sz.Add(self.yaml_txt, flag=wx.TOP | wx.EXPAND, border=5)

        self.main_sz.Add(execution_sz, 1, flag=wx.ALL | wx.EXPAND, border=10)


    def OnAnalyze(self, event):  # pyright: ignore
        router_gen = RouterGen()
        sel_analysis: SelectionAnalysis = router_gen.get_selection_analysis()
        self.info_footprints.SetLabelText(str(sel_analysis.fp_count) + ' ' + (str(sel_analysis.fps) if len(sel_analysis.fps) != 0 else ''))
        self.info_tracks.SetLabelText(str(sel_analysis.tracks_count))
        self.info_vias.SetLabelText(str(sel_analysis.vias_count))
        self.info_unsupported.SetLabelText(
            str(sel_analysis.unsupported_count)
            + " "
            + (
                str(sel_analysis.unsupported_types)
                if len(sel_analysis.unsupported_types) != 0
                else ""
            )
        )
        self.info_nets.SetLabelText(str(len(sel_analysis.nets)) + ' ' + (str(sel_analysis.nets) if len(sel_analysis.nets) != 0 else ''))
        self.set_nets(sel_analysis.nets)
        self.ref_fp.Clear()
        for fp in sel_analysis.fps:
            self.ref_fp.Append(fp)
        self.ref_fp.Value = sel_analysis.default_fp
        if sel_analysis.tracks_count == 0 and sel_analysis.vias_count == 0 and sel_analysis.fp_count != 0:
            self.collect_fp_tracks.SetValue(True)
            self.include_selected_tracks.SetValue(False)

    def OnGenRoute(self, event):  # pyright: ignore
        router_gen = RouterGen()
        self.yaml_txt.SetValue(router_gen.get_selection_router_config(self.ref_fp.GetValue(),
                                                                      self.get_nets_map(),
                                                                      self.collect_fp_tracks.GetValue(),
                                                                      self.include_selected_tracks.GetValue(),
                                                                      self.include_locked_tracks_vias.GetValue(),
                                                                      self.place_nets.GetValue(),
                                                                      self.tab_size.GetValue(),
                                                                      self.fp_sec_name.GetValue(),
                                                                      self.filter.GetValue()))

    def OnClearYaml(self, event):  # pyright: ignore
        self.yaml_txt.SetValue(INSTRUCTIONS)

    def OnCopyToClipboard(self, event):  # pyright: ignore
        sel_str = self.yaml_txt.GetStringSelection()
        value = '' 
        if sel_str != '':
            value = sel_str
        else:
            value = self.yaml_txt.GetValue()

        yaml_lines:list[str] = value.split('\n')
        if len(yaml_lines) > 0:
            if yaml_lines[0] == "footprints:":
                yaml_lines.pop(0)
            for idx, line in enumerate(yaml_lines):
                yaml_lines[idx] = self.tab_size.GetValue()*2*' '+line
        txt_to_copy = "\n".join(yaml_lines) +"\n"

        if wx.TheClipboard.IsOpened():
            wx.TheClipboard.Close()
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(txt_to_copy))
            wx.TheClipboard.Close()


    def OnClose(self, event):
        event.Skip()


# app = wx.App()
# window = ErgogenFrame()
# window.Show()
#
# app.MainLoop()
