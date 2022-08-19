# -*- coding: utf-8 -*-
import abc
from curses import KEY_ENTER
import datetime
import functools
from json import JSONEncoder
from lib2to3.pgen2.token import BACKQUOTE
import logging
import os
import re
# from signal import CTRL_BREAK_EVENT
import sys
import time
from typing import Type, Union

import hashlib
import binascii

import easyutils
# from pywinauto import findwindows, timings

from easytrader import pop_dialog_handler_mac_ths, refresh_strategies
from easytrader.config import client
from easytrader.log import logger
from easytrader.refresh_strategies import IRefreshStrategy
from easytrader.utils.misc import file2dict
from easytrader.utils.perf import perf_clock
import atomacos
from atomacos.keyboard import *
import pywinauto


class IClientTrader(abc.ABC):
    @property
    @abc.abstractmethod
    def app(self):
        """Return current app instance"""
        pass

    @property
    @abc.abstractmethod
    def main(self):
        """Return current main window instance"""
        pass

    @property
    @abc.abstractmethod
    def config(self):
        """Return current config instance"""
        pass

    @abc.abstractmethod
    def wait(self, seconds: float):
        """Wait for operation return"""
        pass

    @abc.abstractmethod
    def refresh(self):
        """Refresh data"""
        pass

    @abc.abstractmethod
    def is_exist_pop_dialog(self):
        pass


class MACClientTrader(IClientTrader):
    _editor_need_type_keys = False
    refresh_strategy: IRefreshStrategy = refresh_strategies.Switch()

    def enable_type_keys_for_editor(self):
        """
        有些客户端无法通过 set_edit_text 方法输入内容，可以通过使用 type_keys 方法绕过
        """
        self._editor_need_type_keys = True

    def __init__(self):
        self._config = client.create(self.broker_type)
        self._app = None
        self._main = None
        self._toolbar = None

    @property
    def app(self):
        return self._app

    @property
    def main(self):
        return self._main

    @property
    def config(self):
        return self._config

    def connect(self, exe_path=None, **kwargs):
        """
        直接连接登陆后的客户端
        :param exe_path: 客户端路径类似 r'C:\\htzqzyb2\\xiadan.exe', 默认 r'C:\\htzqzyb2\\xiadan.exe'
        :return:
        """
        connect_path = exe_path or self._config.DEFAULT_EXE_PATH
        if connect_path is None:
            raise ValueError(
                "参数 exe_path 未设置，请设置客户端对应的 exe 地址,类似 C:\\客户端安装目录\\xiadan.exe"
            )

        print("开始启动程序")
        if sys.platform.startswith("darwin"):
            atomacos.launchAppByBundleId("cn.com.10jqka.macstockPro")
            self._app = atomacos.getAppRefByBundleId(
                "cn.com.10jqka.macstockPro")
            self._main = self._app.windows()[0]
            # self._main = self._app.AXFocusedWindow
            print('成功获取到程序实例')
        else:
            self._app = pywinauto.Application().connect(path=connect_path, timeout=10)
            # self._close_prompt_windows()
            # self._main = self._app.top_window()
            self._main = self._app
            self._init_toolbar()

    @property
    def broker_type(self):
        return "ths_mac"

    @property
    def balance(self):
        self._switch_left_menus(['交易'])
        return self._get_balance_from_statics()

    def _init_toolbar(self):
        self._toolbar = self._main.child_window(class_name="ToolbarWindow32")

    def _get_balance_from_statics(self):
        # 横版表格
        # self._main.findFirstR(AXRole='AXTable').AXRows[6].findAllR(AXRole='AXStaticText')
        result = {}
        table = self._main.findFirstR(AXRole='AXTable')
        # print('获取到表格')
        for key, control_id in self._config.BALANCE_CONTROL_ID_GROUP.items():
            result[key] = float(
                self._main.findFirstR(
                    AXRole='AXTable').AXChildren[control_id].AXChildren[1].AXChildren[0].AXValue
                # table.AXRows[control_id].findAllR(
                #     AXRole='AXStaticText')[1].AXValue
            )
            print("获取表格行: {} - {} - {}".format(control_id, key, result[key]))
        return result

    @property
    def position(self):
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "持仓"])
        return self._get_data_from_table("position")
        # "position": 2,
        # "entrusts": 3,
        # "trades": 4

    def _get_grid_table(self):
        return self._main.findFirstR(AXRole='AXGroup').AXParent

    def _get_data_from_table(self, control):
        # table = self._main.findAllR(AXRole='AXTable')[
        #     self.config.TABLE_CONTROL_ID[control]]
        # table = self._main.AXChildren[self.config.TABLE_CONTROL_ID[control]].AXChildren[0]
        table = self._get_grid_table()  # self._main.findFirstR(AXRole='AXGroup').AXParent
        result = []
        titles = table.AXHeader.findAllR(AXRole='AXButton')
        for row in table.AXRows:
            col = row.findAllR(AXRole='AXStaticText')
            rowdata = {}
            clen = len(col)
            for l in range(0, clen-1):
                rowdata[titles[l].AXTitle] = col[l].AXValue

            result.append(rowdata)
            # print("获取表格数据: {} - {}".format(control, result))
        return result

    @ property
    def today_entrusts(self):
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "委托"])
        return self._get_data_from_table("entrusts")

    @ property
    def today_trades(self):
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "成交"])
        return self._get_data_from_table("trades")

    @ property
    def cancel_entrusts(self):
        # TODO
        # self.refresh()
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "委托"])
        return self._get_grid_table()

    @ perf_clock
    def cancel_entrust(self, entrust_no):
        # TODO
        # self.refresh()
        # for i, entrust in enumerate(self.cancel_entrusts):
        #     if entrust[self._config.CANCEL_ENTRUST_ENTRUST_FIELD] == entrust_no:
        #         self._cancel_entrust_by_double_click(i)
        #         return self._handle_pop_dialogs()
        # return {"message": "委托单状态错误不能撤单, 该委托单可能已经成交或者已撤"}
        table = self.cancel_entrusts
        for row in table.AXRows:
            col = row.findAllR(AXRole='AXStaticText')
            # titles = table.AXHeader.findFirstR(AXRole='AXButton',AXTitle = '')
            # rowdata = {}
            # clen = len(col)
            # for l in range(0, clen-1):
            #     rowdata[titles[l].AXTitle] = col[l].AXValue
            if col[2].AXValue == entrust_no:
                print("证券代码{}".format(entrust_no))
                position = row.AXPosition
                height = row.AXSize.height
                width = row.AXSize.width
                atomacos.mouse.doubleClick(
                    position.x + width/2, position.y + height / 2)
                self.confirm_pop_dialog()

            # result.append(rowdata)
            # print("获取表格数据: {} - {}".format(control, result))
        # return result

    def cancel_all_entrusts(self):
        # self.refresh()
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "委托", "全撤"])
        # 点击全部撤销控件
        self.wait(0.2)
        self.confirm_pop_dialog()

    def cancel_all_buy_entrusts(self):
        # self.refresh()
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "委托", "撤买"])
        # 点击全部撤销控件
        self.wait(0.2)
        self.confirm_pop_dialog()

    def cancel_all_sell_entrusts(self):
        # self.refresh()
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "委托", "撤卖"])
        # 点击全部撤销控件
        self.wait(0.2)
        self.confirm_pop_dialog()

    @perf_clock
    def confirm_pop_dialog(self):
        # 等待出现 确认兑换框
        if self.is_exist_pop_dialog():
            # 点击是 按钮
            w = self._app.AXFocusedWindow
            w.findFirstR(AXRole='AXButton', AXTitle='确认').Press()
            self.wait(0.2)
            # 如果出现了确认窗口
            self.close_pop_dialog()

    @ perf_clock
    def repo(self, security, price, amount, **kwargs):
        self._switch_left_menus(["债券回购", "融资回购（正回购）"])

        return self.trade(security, price, amount)

    @ perf_clock
    def reverse_repo(self, security, price, amount, **kwargs):
        self._switch_left_menus(["债券回购", "融劵回购（逆回购）"])

        return self.trade(security, price, amount)

    @ perf_clock
    def buy(self, security, price, amount, **kwargs):

        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "买入"])
        print('进行交易{}-{}-{}'.format(security, price, amount))

        res = self.trade(security, price, amount, 0)
        print("买入结果-{}".format(res))
        # if res:
        #     self._submit_trade("确定买入")

    @ perf_clock
    def sell(self, security, price, amount, **kwargs):
        self._switch_left_menus(["交易", self._config.TRADER_TYPE, "卖出"])

        res = self.trade(security, price, amount, 1)
        print("卖出结果-{}".format(res))
        return res

    @ perf_clock
    def market_buy(self, security, amount, ttype=None, limit_price=None, **kwargs):
        """
        市价买入
        :param security: 六位证券代码
        :param amount: 交易数量
        :param ttype: 市价委托类型，默认客户端默认选择，
                     深市可选 ['对手方最优价格', '本方最优价格', '即时成交剩余撤销', '最优五档即时成交剩余 '全额成交或撤销']
                     沪市可选 ['最优五档成交剩余撤销', '最优五档成交剩余转限价']
        :param limit_price: 科创板 限价

        :return: {'entrust_no': '委托单号'}
        """
        self._switch_left_menus(["市价委托", "买入"])

        return self.market_trade(security, amount, ttype, limit_price=limit_price)

    @ perf_clock
    def market_sell(self, security, amount, ttype=None, limit_price=None, **kwargs):
        """
        市价卖出
        :param security: 六位证券代码
        :param amount: 交易数量
        :param ttype: 市价委托类型，默认客户端默认选择，
                     深市可选 ['对手方最优价格', '本方最优价格', '即时成交剩余撤销', '最优五档即时成交剩余 '全额成交或撤销']
                     沪市可选 ['最优五档成交剩余撤销', '最优五档成交剩余转限价']
        :param limit_price: 科创板 限价
        :return: {'entrust_no': '委托单号'}
        """
        self._switch_left_menus(["市价委托", "卖出"])

        return self.market_trade(security, amount, ttype, limit_price=limit_price)

    def market_trade(self, security, amount, ttype=None, limit_price=None, **kwargs):
        """
        市价交易
        :param security: 六位证券代码
        :param amount: 交易数量
        :param ttype: 市价委托类型，默认客户端默认选择，
                     深市可选 ['对手方最优价格', '本方最优价格', '即时成交剩余撤销', '最优五档即时成交剩余 '全额成交或撤销']
                     沪市可选 ['最优五档成交剩余撤销', '最优五档成交剩余转限价']

        :return: {'entrust_no': '委托单号'}
        """
        code = security[-6:]
        self._type_edit_control_keys(
            self._config.TRADE_SECURITY_CONTROL_ID, code)
        if ttype is not None:
            retry = 0
            retry_max = 10
            while retry < retry_max:
                try:
                    self._set_market_trade_type(ttype)
                    break
                except:
                    retry += 1
                    self.wait(0.1)
        self._set_market_trade_params(
            security, amount, limit_price=limit_price)
        self._submit_trade()

        return self._handle_pop_dialogs(
            handler_class=pop_dialog_handler_mac_ths.TradePopDialogHandler
        )

    def _set_market_trade_type(self, ttype):
        """根据选择的市价交易类型选择对应的下拉选项"""
        selects = self._main.child_window(
            control_id=self._config.TRADE_MARKET_TYPE_CONTROL_ID, class_name="ComboBox"
        )
        for i, text in enumerate(selects.texts()):
            # skip 0 index, because 0 index is current select index
            if i == 0:
                if re.search(ttype, text):  # 当前已经选中
                    return
                else:
                    continue
            if re.search(ttype, text):
                selects.select(i - 1)
                return
        raise TypeError("不支持对应的市价类型: {}".format(ttype))

    def _set_stock_exchange_type(self, ttype):
        """根据选择的市价交易类型选择对应的下拉选项"""
        selects = self._main.child_window(
            control_id=self._config.TRADE_STOCK_EXCHANGE_CONTROL_ID, class_name="ComboBox"
        )

        for i, text in enumerate(selects.texts()):
            # skip 0 index, because 0 index is current select index
            if i == 0:
                if ttype.strip() == text.strip():  # 当前已经选中
                    return
                else:
                    continue
            if ttype.strip() == text.strip():
                selects.select(i - 1)
                return
        raise TypeError("不支持对应的市场类型: {}".format(ttype))

    def auto_ipo(self):
        self._switch_left_menus(self._config.AUTO_IPO_MENU_PATH)

        stock_list = self._get_grid_data(self._config.COMMON_GRID_CONTROL_ID)

        if len(stock_list) == 0:
            return {"message": "今日无新股"}
        invalid_list_idx = [
            i for i, v in enumerate(stock_list) if v[self.config.AUTO_IPO_NUMBER] <= 0
        ]

        if len(stock_list) == len(invalid_list_idx):
            return {"message": "没有发现可以申购的新股"}

        self._click(self._config.AUTO_IPO_SELECT_ALL_BUTTON_CONTROL_ID)
        self.wait(0.1)

        for row in invalid_list_idx:
            self._click_grid_by_row(row)
        self.wait(0.1)

        self._click(self._config.AUTO_IPO_BUTTON_CONTROL_ID)
        self.wait(0.1)

        return self._handle_pop_dialogs()

    def _click_grid_by_row(self, row):
        x = self._config.COMMON_GRID_LEFT_MARGIN
        y = (
            self._config.COMMON_GRID_FIRST_ROW_HEIGHT
            + self._config.COMMON_GRID_ROW_HEIGHT * row
        )
        self._app.top_window().child_window(
            control_id=self._config.COMMON_GRID_CONTROL_ID,
            class_name="CVirtualGridCtrl",
        ).click(coords=(x, y))

    @ perf_clock
    def is_exist_pop_dialog(self):
        self.wait(0.5)  # wait dialog display
        try:
            res = (
                # self._app.findFirstR(AXRole='AXSheet') is not None
                self._app.AXFocusedWindow != self._main
            )
            print("是否存在弹窗-{}".format(res))
            return res
        except (
            # findwindows.ElementNotFoundError,
            # timings.TimeoutError,
            RuntimeError,
        ) as ex:
            logger.exception("check pop dialog timeout")
            return False

    @ perf_clock
    def close_pop_dialog(self):
        try:
            if self.is_exist_pop_dialog():
                w = self.app.AXFocusedWindow
                w2 = self.app.AXChildren[0]
                if w != w2:
                    atomacos.mouse.click(w.AXPosition)
                    self._main = w
                    self.wait(0.2)
                else:
                    w = self._app.findFirstR(AXRole='AXSheet')
                    if w is not None:
                        w.findFirstR(AXRole='AXButton', AXTitle='取消').Press()
                        self.wait(0.2)

        except (
                # findwindows.ElementNotFoundError,
                # timings.TimeoutError,
                RuntimeError,
        ) as ex:
            pass

    def _run_exe_path(self, exe_path):
        return os.path.join(os.path.dirname(exe_path), "xiadan.exe")

    def wait(self, seconds):
        time.sleep(seconds)

    def exit(self):
        self._app.kill()

    def _close_prompt_windows(self):
        self.wait(1)
        for window in self._app.windows(class_name="#32770", visible_only=True):
            title = window.window_text()
            if title != self._config.TITLE:
                logging.info("close " + title)
                window.close()
                self.wait(0.2)
        self.wait(1)

    def close_pormpt_window_no_wait(self):
        for window in self._app.windows(class_name="#32770"):
            if window.window_text() != self._config.TITLE:
                window.close()

    def trade(self, security, price, amount, options=0):
        self._set_trade_params(security, price, amount)
        self._submit_trade(options)

        return self._handle_pop_dialogs(
            handler_class=pop_dialog_handler_mac_ths.TradePopDialogHandler
        )

    def _click(self, control_id):
        self._app.top_window().child_window(
            control_id=control_id, class_name="Button"
        ).click()

    @ perf_clock
    def _submit_trade(self, options):
        self.wait(0.2)
        if options == 1:
            self._main.findFirstR(AXRole='AXButton', AXTitle='确定卖出').Press()
        elif options == 0:
            self._main.findFirstR(AXRole='AXButton', AXTitle='确定买入').Press()

    @ perf_clock
    def __get_top_window_pop_dialog(self):
        return self._app.top_window().window(
            control_id=self._config.POP_DIALOD_TITLE_CONTROL_ID
        )

    @ perf_clock
    def _get_pop_dialog_title(self):
        return (
            self._app.AXFocusedWindow.AXChildren[1].AXValue
            # self._app.findFirstR(AXRole='AXSheet')
            # .findFirstR(
            #     AXRole='AXStaticText').AXValue
        )

    def _set_trade_params(self, security, price, amount):
        code = security[-6:]

        print("进行股票代码输入{}".format(code))
        self._type_edit_control_keys(
            self._config.TRADE_SECURITY_CONTROL_ID, code)
        print("完成股票代码输入{}".format(code))

        # wait security input finish
        # self.wait(0.1)

        # 设置交易所
        # if security.lower().startswith("sz"):
        #     self._set_stock_exchange_type("深圳Ａ股")
        # if security.lower().startswith("sh"):
        #     self._set_stock_exchange_type("上海Ａ股")

        # self.wait(0.1)

        print("进行价格输入{}".format(price))
        self._type_edit_control_keys(
            self._config.TRADE_PRICE_CONTROL_ID,
            easyutils.round_price_by_code(price, code),
        )
        print("完成价格输入{}".format(price))
        # self.wait(0.1)
        print("进行数量输入{}".format(amount))
        self._type_edit_control_keys(
            self._config.TRADE_AMOUNT_CONTROL_ID, str(int(amount))
        )
        print("完成数量输入{}".format(amount))

    def _set_market_trade_params(self, security, amount, limit_price=None):
        self._type_edit_control_keys(
            self._config.TRADE_AMOUNT_CONTROL_ID, str(int(amount))
        )
        self.wait(0.1)
        price_control = None
        if str(security).startswith("68"):  # 科创板存在限价
            try:
                price_control = self._main.child_window(
                    control_id=self._config.TRADE_PRICE_CONTROL_ID, class_name="Edit"
                )
            except:
                pass
        if price_control is not None:
            price_control.set_edit_text(limit_price)

    def _get_grid_data(self, control_id):
        return self.grid_strategy_instance.get(control_id)

    def _type_keys(self, control_id, text):
        self._main.child_window(control_id=control_id, class_name="Edit").set_edit_text(
            text
        )

    def _type_edit_control_keys(self, control_id, text):

        print("进行输入框获取-{}-{}".format(control_id, time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime())))
        # input = self._main.findFirstR(
        #     AXRole='AXTextField', AXNumberOfCharacters=control_id)
        input = self._main.AXChildren[control_id]
        print("完成输入框获取-{}-{}".format(control_id, time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime())))
        input_position = input.AXPosition
        print("输入框position-{}-{}".format(control_id, input_position))
        atomacos.mouse.click(input_position)
        atomacos.keyboard.hotkey('command', 'a')
        atomacos.keyboard.keyDown('backspace')
        # self.wait(0.5)

        # 输入文本
        # atomacos.keyboard.typewrite('002119')
        atomacos.keyboard.typewrite(text)  # , interval=0.1)
        # input.sendKeys(text)
        # 空格
        # input.sendKeys([BACKSPACE])
        print("完成输入框赋值{}-{}".format(control_id, text))

    def type_edit_control_keys(self, editor, text):
        if not self._editor_need_type_keys:
            editor.set_edit_text(text)
        else:
            editor.select()
            editor.type_keys(text)

    def _collapse_left_menus(self):
        items = self._get_left_menus_handle().roots()
        for item in items:
            item.collapse()

    @ perf_clock
    def _switch_left_menus(self, path, sleep=0.2):
        print('菜单点击{}'.format(path))
        if self.is_exist_pop_dialog():
            self.close_pop_dialog()
        for i in range(len(path)):
            if i == 0:
                self._main.buttons()[self.config.LEFT_MENU_ID[path[i]]].Press()
            else:
                self._main.findFirstR(
                    AXRole='AXButton', AXTitle=path[i]).Press()
            # self.close_pop_dialog()
            # self._get_left_menus_handle().get_item(path).select()
            # self._app.top_window().type_keys('{F5}')
            self.wait(sleep)

    def _switch_left_menus_by_shortcut(self, shortcut, sleep=0.5):
        self.close_pop_dialog()
        # self._app.top_window().type_keys(shortcut)
        self.wait(sleep)

    @ functools.lru_cache()
    def _get_left_menus_handle(self):
        count = 2
        while True:
            try:
                handle = self._main.child_window(
                    control_id=129, class_name="SysTreeView32"
                )
                if count <= 0:
                    return handle
                # sometime can't find handle ready, must retry
                handle.wait("ready", 2)
                return handle
            # pylint: disable=broad-except
            except Exception as ex:
                logger.exception(
                    "error occurred when trying to get left menus")
            count = count - 1

    def _cancel_entrust_by_double_click(self, row):
        x = self._config.CANCEL_ENTRUST_GRID_LEFT_MARGIN
        y = (
            self._config.CANCEL_ENTRUST_GRID_FIRST_ROW_HEIGHT
            + self._config.CANCEL_ENTRUST_GRID_ROW_HEIGHT * row
        )
        self._app.top_window().child_window(
            control_id=self._config.COMMON_GRID_CONTROL_ID,
            class_name="CVirtualGridCtrl",
        ).double_click(coords=(x, y))

    def refresh(self):
        self.refresh_strategy.set_trader(self)
        self.refresh_strategy.refresh()

    @ perf_clock
    def _handle_pop_dialogs(self, handler_class=pop_dialog_handler_mac_ths.PopDialogHandler):
        handler = handler_class(self._app)

        print("开始获取弹窗")
        while self.is_exist_pop_dialog():
            try:
                print("开始获取标题")
                title = self._get_pop_dialog_title()
                print("完成获取标题-{}".format(title))
            except Exception as e:  # pywinauto.findwindows.ElementNotFoundError:
                print("标题获取异常".format(e))
                return {"message": "success"}
            print("开始处理{}弹窗".format(title))
            result = handler.handle(title)
            print("完成处理{}弹窗-{}".format(title, result))
            if result:
                return result
        return {'message': 'success'}


class BaseLoginClientTrader(MACClientTrader):
    @ abc.abstractmethod
    def login(self, user, password, exe_path, comm_password=None, **kwargs):
        """Login Client Trader"""
        pass

    def prepare(
        self,
        config_path=None,
        user=None,
        password=None,
        exe_path=None,
        comm_password=None,
        **kwargs
    ):
        """
        登陆客户端
        :param config_path: 登陆配置文件，跟参数登陆方式二选一
        :param user: 账号
        :param password: 明文密码
        :param exe_path: 客户端路径类似 r'C:\\htzqzyb2\\xiadan.exe', 默认 r'C:\\htzqzyb2\\xiadan.exe'
        :param comm_password: 通讯密码
        :return:
        """
        if config_path is not None:
            account = file2dict(config_path)
            user = account["user"]
            password = account["password"]
            comm_password = account.get("comm_password")
            exe_path = account.get("exe_path")
        self.login(
            user,
            password,
            exe_path or self._config.DEFAULT_EXE_PATH,
            comm_password,
            **kwargs
        )
        self._init_toolbar()


if __name__ == '__main__':
    trader = MACClientTrader()
    trader.connect()
    # balance = trader.balance
    # print(balance)
    # position = trader.position
    # print(position)
    entrusts = trader.today_entrusts
    print(entrusts)
    # trades = trader.today_trades
    # print(trades)
    trader.buy('zh002119', '8.31', '100')
    trader.buy('zh002119', '8.31', '100')
    # trader.sell('zh002119', '16.89', '1')
    # trader.cancel_all_buy_entrusts()
    # trader.cancel_all_sell_entrusts()
    # trader.cancel_all_entrusts()
    # trader.cancel_entrust(entrust_no='002219')
