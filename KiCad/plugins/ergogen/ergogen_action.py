import pcbnew
from typing import Union
import wx

from .ergogen_frame import ErgogenFrame

from .helper import get_logger
logger = get_logger(__name__)


class ErgogenPluginAction(pcbnew.ActionPlugin):
    window: Union[wx.Frame, None] = None

    def defaults(self):
        self.name = "Ergogen - Ergonomic Keyboard Generator KiCad Plugin"
        self.category = "A descriptive category name"
        self.description = "Extracts routes for use in ErgoGen config file"
        self.show_toolbar_button = False  # Optional, defaults to False
        # self.icon_file_name = os.path.join(os.path.dirname(
        #     __file__), 'simple_plugin.png')  # Optional, defaults to ""

    def Run(self):
        if self.window is None:
            self.init_window()
        else:
            self.window.Raise()

    def init_window(self):
        self.window = ErgogenFrame()
        self.window.Show(True)
        self.window.Bind(wx.EVT_CLOSE, self.OnWindowClose)

    def OnWindowClose(self, event):
        logger.debug("Ergogen Frame was closed, marking in Ergogen Action")
        self.window = None
        event.Skip()

