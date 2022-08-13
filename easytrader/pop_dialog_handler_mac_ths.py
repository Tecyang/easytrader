# coding:utf-8
import re
import time
import sys
from typing import Optional

from easytrader import exceptions
from easytrader.utils.perf import perf_clock
from atomacos.keyboard import *

if not sys.platform.startswith("darwin"):
    from easytrader.utils.win_gui import SetForegroundWindow, ShowWindow, win32defines


class PopDialogHandler:
    def __init__(self, app):
        self._app = app

    @staticmethod
    def _set_foreground(window):
        if window.has_style(win32defines.WS_MINIMIZE):  # if minimized
            ShowWindow(window.wrapper_object(), 9)  # restore window state
        else:
            SetForegroundWindow(window.wrapper_object())  # bring to front

    @perf_clock
    def handle(self, title):
        print('处理弹窗-{}'.format(title))
        if any(s in title for s in {"买入委托", "卖出委托"}):
            self._submit_by_shortcut()
            return True

        if "警告" in title:
            content = self._extract_content()
            # self._submit_by_shortcut()
            self._submit_by_click()
            return {"message": content}

        content = self._extract_content()
        self._close()
        return {"message": "unknown message: {}".format(content)}

    def _extract_content(self):
        return self._app.AXFocusedWindow.AXChildren[2].AXValue
        # return self._app.top_window().Static.window_text()

    @staticmethod
    def _extract_entrust_id(content):
        return re.search(r"[\da-zA-Z]+", content).group()

    def _submit_by_click(self):
        try:
            self._app.AXFocusedWindow.AXChildren[3].Press()
        except Exception as ex:
            print(ex)

    def _submit_by_shortcut(self):
        # todo
        # self._set_foreground(self._app.top_window())
        # self._app.top_window().type_keys("%Y", set_foreground=False)
        print("快捷键提交")
        self._app.sendKeys(['enter'])

    def _close(self):
        self._app.sendKeys(['esc'])


class TradePopDialogHandler(PopDialogHandler):
    @perf_clock
    def handle(self, title) -> Optional[dict]:
        print('处理弹窗-{}'.format(title))
        if title == "买入委托" or title == "卖出委托":
            self._submit_by_shortcut()
            return None

        if "警告" in title:
            content = self._extract_content()
            # self._submit_by_shortcut()
            self._submit_by_click()
            return {'message': content}
            # raise exceptions.TradeError(content)

        if "确认" in title:
            self._submit_by_shortcut()
            # self._submit_by_click()
            time.sleep(0.05)
            raise exceptions.TradeError(content)
        self._close()
        return None
