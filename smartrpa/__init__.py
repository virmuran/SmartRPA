"""SmartRPA - 视觉驱动的智能桌面自动化程序"""
from .core.controller import Controller
from .core.vision import Vision, Found
from .core.engine import TaskEngine
from .core.behavior_tree import BTEngine
from .core.popup import PopupHandler
from .core.human import HumanLike

__version__ = "0.8.0"
__all__ = ['Controller', 'Vision', 'Found', 'TaskEngine', 'BTEngine',
           'PopupHandler', 'HumanLike']
