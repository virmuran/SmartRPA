"""SmartRPA - 视觉驱动的智能桌面自动化程序"""
from .core.controller import Controller
from .core.vision import Vision, Found
from .core.engine import TaskEngine
from .core.popup import PopupHandler
from .core.human import HumanLike

__version__ = "0.6.4"
__all__ = ['Controller', 'Vision', 'Found', 'TaskEngine', 'PopupHandler', 'HumanLike']
