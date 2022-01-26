import time

from . import config
from . import detector
from .device import Device, KeyCode
from .log import logger
from .recognize import Recognizer, Scene, RecognizeError
from ..utils.typealias import Coordinate


class StrategyError(Exception):
    """ Strategy Error """
    pass


class BaseSolver:
    """ Base class, provide basic operation """

    def __init__(self, device: Device = None, recog: Recognizer = None) -> None:
        self.device = device if device is not None else (recog.device if recog is not None else Device())
        self.recog = recog if recog is not None else Recognizer(self.device)
        if self.device.current_focus() != config.APPNAME:
            self.device.launch(config.APPNAME)
            # wait for app to finish launching
            time.sleep(10)
    
    def get_color(self, pos: Coordinate):
        """ get the color of the pixel """
        return self.recog.color(pos[0], pos[1])

    def get_pos(self, poly, x_rate=0.5, y_rate=0.5):
        if poly is None:
            raise RecognizeError
        elif len(poly) == 4:
            x = (poly[0][0] * (1-x_rate) + poly[1][0] * (1-x_rate) +
                 poly[2][0] * x_rate + poly[3][0] * x_rate) / 2
            y = (poly[0][1] * (1-y_rate) + poly[3][1] * (1-y_rate) +
                 poly[1][1] * y_rate + poly[2][1] * y_rate) / 2
        elif len(poly) == 2 and type(poly[0]).__name__ in ['list', 'tuple']:
            x = poly[0][0] * (1-x_rate) + poly[1][0] * x_rate
            y = poly[0][1] * (1-y_rate) + poly[1][1] * y_rate
        else:
            x, y = poly
        return (int(x), int(y))

    def sleep(self, interval=1, matcher=True):
        time.sleep(interval)
        self.recog.update(matcher=matcher)  # TODO

    def input(self, text, input_area):
        logger.debug(f'input: {text} {input_area}')
        self.device.tap(self.get_pos(input_area))
        self.device.send_text(input(text).strip())
        self.device.tap((0, 0))

    def find(self, item, draw=False, scope=None, thres=None, judge=True):
        return self.recog.find(item, draw, scope, thres, judge)

    def tap(self, poly, x_rate=0.5, y_rate=0.5, interval=1, matcher=True):
        pos = self.get_pos(poly, x_rate, y_rate)
        self.device.tap(pos)
        if interval > 0:
            self.sleep(interval, matcher=matcher)

    def tap_element(self, element_name, x_rate=0.5, y_rate=0.5, interval=1, draw=False, scope=None, detected=False, judge=True, matcher=True):
        if element_name == 'nav_button':
            element = self.recog.nav_button()
        else:
            element = self.recog.find(element_name, draw, scope, judge=judge)
        if detected and element is None:
            return False
        self.tap(element, x_rate, y_rate, interval, matcher)
        return True

    def swipe(self, start, movement, duration=100, interval=1, matcher=True):
        end = (start[0] + movement[0], start[1] + movement[1])
        self.device.swipe([start, end], duration=duration)
        if interval > 0:
            self.sleep(interval, matcher=matcher)

    def swipe_seq(self, points, duration=100, interval=1, matcher=True):
        self.device.swipe(points, duration=duration)
        if interval > 0:
            self.sleep(interval, matcher=matcher)

    def swipe_move(self, start, movements, duration=100, interval=1, matcher=True):
        points = [start]
        for move in movements:
            points.append((points[-1][0] + move[0], points[-1][1] + move[1]))
        self.device.swipe(points, duration=duration)
        if interval > 0:
            self.sleep(interval, matcher=matcher)

    def back(self, interval=1, matcher=True):
        self.device.send_keyevent(KeyCode.KEYCODE_BACK)
        self.sleep(interval=interval, matcher=matcher)

    def scene(self):
        return self.recog.get_scene()

    def is_login(self):
        return not (self.scene() // 100 == 1 or self.scene() // 100 == 99 or self.scene() == -1)

    def login(self):
        """
        登录进游戏
        """
        retry_times = config.MAX_RETRYTIME
        while retry_times and self.is_login() == False:
            try:
                if self.scene() == Scene.LOGIN_START:
                    self.tap((self.recog.w // 2, self.recog.h - 10), 3)
                elif self.scene() == Scene.LOGIN_QUICKLY:
                    self.tap_element('login_awake')
                elif self.scene() == Scene.LOGIN_MAIN:
                    self.tap_element('login_account')
                elif self.scene() == Scene.LOGIN_INPUT:
                    input_area = self.recog.find('login_username')
                    if input_area is not None:
                        self.input('Enter username: ', input_area)
                    input_area = self.recog.find('login_password')
                    if input_area is not None:
                        self.input('Enter password: ', input_area)
                    self.tap_element('login_button')
                elif self.scene() == Scene.LOGIN_ANNOUNCE:
                    self.tap_element('login_iknow')
                elif self.scene() == Scene.LOGIN_LOADING:
                    self.sleep(3)
                elif self.scene() == Scene.LOADING:
                    self.sleep(3)
                elif self.scene() == Scene.CONFIRM:
                    self.tap(detector.confirm(self.recog.img))
                else:
                    raise RecognizeError
            except RecognizeError as e:
                logger.warning(f'识别出了点小差错 qwq: {e}')
                retry_times -= 1
                self.sleep(3)
                continue
            except Exception as e:
                raise e
            retry_times = config.MAX_RETRYTIME

        if not self.is_login():
            raise StrategyError

    def get_navigation(self):
        """
        判断是否存在导航栏，若存在则打开
        """
        while True:
            if self.scene() == Scene.NAVIGATION_BAR:
                return True
            else:
                if not self.tap_element('nav_button', detected=True):
                    return False

    def back_to_index(self):
        """
        返回主页
        """
        logger.info('back to index')
        retry_times = config.MAX_RETRYTIME
        while retry_times and self.scene() != Scene.INDEX:
            try:
                if self.get_navigation():
                    self.tap_element('nav_index')
                elif self.scene() == Scene.ANNOUNCEMENT:
                    self.tap(detector.announcement_close(self.recog.img))
                elif self.scene() == Scene.MATERIEL:
                    self.tap_element('materiel_ico')
                elif self.scene() // 100 == 1:
                    self.login()
                elif self.scene() == Scene.CONFIRM:
                    self.tap(detector.confirm(self.recog.img))
                elif self.scene() == Scene.LOADING:
                    self.sleep(3)
                elif self.scene() == Scene.SKIP:
                    self.tap_element('skip')
                elif self.scene() == Scene.OPERATOR_ONGOING:
                    self.sleep(10)
                elif self.scene() == Scene.OPERATOR_FINISH:
                    self.tap((self.recog.w // 2, 10))
                elif self.scene() == Scene.OPERATOR_ELIMINATE_FINISH:
                    self.tap((self.recog.w // 2, 10))
                elif self.scene() == Scene.DOUBLE_CONFIRM:
                    self.tap_element('double_confirm', 0.8)
                elif self.scene() == Scene.MAIL:
                    mail = self.recog.find('mail')
                    mid_y = (mail[0][1] + mail[1][1]) // 2
                    self.tap((mid_y, mid_y))
                else:
                    raise RecognizeError
            except RecognizeError as e:
                logger.warning(f'识别出了点小差错 qwq: {e}')
                retry_times -= 1
                self.sleep(3)
                continue
            except Exception as e:
                raise e
            retry_times = config.MAX_RETRYTIME

        if self.scene() != Scene.INDEX:
            raise StrategyError
