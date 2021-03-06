from __future__ import print_function
import threading
import pytest
import time

import testing_utils
from testing_utils import call_gui_callback, wait_for_gui
from rafcon.utils import log

logger = log.get_logger(__name__)
ready = threading.Event()
event_size = (0, 0)


def get_stored_window_size(window_name):
    from rafcon.gui.runtime_config import global_runtime_config
    from rafcon.gui.utils import constants
    size = global_runtime_config.get_config_value(window_name.upper() + '_SIZE')
    if not size:
        size = constants.WINDOW_SIZE[window_name.upper()]
    return size


def notify_on_event(window, event=None):
    logger.info("show/hide event: type={}".format(event.type if event else "None"))
    ready.set()
    return True


def notify_on_resize_event(window, event=None):
    global event_size
    logger.info("resize event: type={} size=({}, {})".format(event.type, event.width, event.height))
    ready.set()
    event_size = (event.width, event.height)


def wait_for_event_notification():
    if not ready.wait(5):
        raise RuntimeError("A timeout occurred")
    # time.sleep(0.1)
    call_gui_callback(wait_for_gui)


def assert_pos_equality(pos1, pos2, allow_delta=10):
    # print "assert_pos_equality: abs(pos1 - pos2)", abs(pos1 - pos2)
    assert abs(pos1 - pos2) <= allow_delta


def assert_size_equality(size1, size2, allow_delta=10):
    assert_pos_equality(size1[0], size2[0], allow_delta)
    assert_pos_equality(size1[1], size2[1], allow_delta)


def connect_window(window, event, method):
    handler_id = call_gui_callback(window.connect, event, method)
    return handler_id


def undock_sidebars():
    from rafcon.gui.runtime_config import global_runtime_config
    from rafcon.gui.singleton import main_window_controller
    debug_sleep_time = 0

    def test_bar(window, window_key):
        attribute_name_of_undocked_window_view = window_name = window_key.lower() + "_window"

        configure_handler_id = connect_window(window, 'configure-event', notify_on_resize_event)
        hide_handler_id = connect_window(window, 'hide', notify_on_event)

        logger.info("undocking...")
        time.sleep(debug_sleep_time)
        ready.clear()
        call_gui_callback(main_window_controller.view["undock_{}_button".format(window_key.lower())].emit, "clicked")
        wait_for_event_notification()
        assert window.get_property('visible') is True
        expected_size = get_stored_window_size(window_name)
        new_size = window.get_size()
        # print dir(window)
        if not bool(window.is_maximized()):
            assert_size_equality(new_size, expected_size, 90)
        else:
            maximized_parameter_name = window_key + "_WINDOW_MAXIMIZED"
            assert bool(window.is_maximized()) and global_runtime_config.get_config_value(maximized_parameter_name)

        logger.info("resizing...")
        time.sleep(debug_sleep_time)
        ready.clear()
        target_size = (1400, 800)
        try:
            assert_size_equality(new_size, target_size, 90)
            # Change target size if it is similar to the current size
            target_size = (1600, 900)
        except AssertionError:
            pass

        logger.debug("target size: {}".format(target_size))
        call_gui_callback(window.resize, *target_size)
        wait_for_event_notification()
        try:
            assert_size_equality(event_size, target_size, 90)
        except AssertionError:
            # For unknown reasons, there are two configure events and only the latter one if for the new window size
            ready.clear()
            wait_for_event_notification()
            assert_size_equality(event_size, target_size, 90)
            logger.info("got additional configure-event")

        logger.info("docking...")
        undocked_window_view = getattr(main_window_controller.view, attribute_name_of_undocked_window_view)
        redock_button = undocked_window_view['redock_button']
        time.sleep(debug_sleep_time)
        ready.clear()
        call_gui_callback(redock_button.emit, "clicked")
        wait_for_event_notification()
        assert window.get_property('visible') is False

        logger.info("undocking...")
        time.sleep(debug_sleep_time)
        ready.clear()

        show_handler_id = connect_window(window, 'show', notify_on_event)

        call_gui_callback(main_window_controller.view["undock_{}_button".format(window_key.lower())].emit, "clicked")
        wait_for_event_notification()
        assert window.get_property('visible') is True
        assert_size_equality(window.get_size(), target_size, 90)

        logger.info("docking...")
        time.sleep(debug_sleep_time)
        ready.clear()
        call_gui_callback(redock_button.emit, "clicked")
        wait_for_event_notification()
        assert window.get_property('visible') is False

        call_gui_callback(window.disconnect, configure_handler_id)
        call_gui_callback(window.disconnect, show_handler_id)
        call_gui_callback(window.disconnect, hide_handler_id)

    print("=> test left_bar_window")
    test_bar(main_window_controller.view.left_bar_window.get_top_widget(), "LEFT_BAR")
    print("=> test right_bar_window")
    test_bar(main_window_controller.view.right_bar_window.get_top_widget(), "RIGHT_BAR")
    print("=> test console_window")
    test_bar(main_window_controller.view.console_window.get_top_widget(), "CONSOLE")
    testing_utils.call_gui_callback(wait_for_gui)


def check_pane_positions():
    from rafcon.gui.singleton import main_window_controller
    from rafcon.gui.runtime_config import global_runtime_config
    from rafcon.gui.utils import constants
    debug_sleep_time = 0.0

    stored_pane_positions = {}
    for config_id, pan_id in constants.PANE_ID.items():
        default_pos = constants.DEFAULT_PANE_POS[config_id]
        stored_pane_positions[config_id] = global_runtime_config.get_config_value(config_id, default_pos)
        if stored_pane_positions[config_id] is None:
            import logging
            logging.warning("runtime_config-file has missing values?")
            return

    def test_bar(window, window_key):

        configure_handler_id = connect_window(window, 'configure-event', notify_on_event)
        hide_handler_id = connect_window(window, 'hide', notify_on_event)

        print("undocking...")
        time.sleep(debug_sleep_time)
        ready.clear()
        call_gui_callback(main_window_controller.view["undock_{}_button".format(window_key.lower())].emit, "clicked")
        wait_for_event_notification()

        print("docking...")
        time.sleep(debug_sleep_time)
        ready.clear()
        attribute_name_of_undocked_window_view = window_key.lower() + "_window"
        undocked_window_view = getattr(main_window_controller.view, attribute_name_of_undocked_window_view)
        redock_button = undocked_window_view['redock_button']
        call_gui_callback(redock_button.emit, "clicked")
        wait_for_event_notification()

        time.sleep(debug_sleep_time)
        call_gui_callback(window.disconnect, configure_handler_id)
        call_gui_callback(window.disconnect, hide_handler_id)

    # Info: un- and redocking the left bar will change the right bar position;
    # thus, the equality check has to be done directly after un- and redocking the right bar
    print("=> test right_bar_window")
    test_bar(main_window_controller.view.right_bar_window.get_top_widget(), "RIGHT_BAR")
    testing_utils.wait_for_gui()
    config_id = 'RIGHT_BAR_DOCKED_POS'
    pane_id = constants.PANE_ID['RIGHT_BAR_DOCKED_POS']
    print("check pos of ", config_id, pane_id)
    assert_pos_equality(main_window_controller.view[pane_id].get_position(), stored_pane_positions[config_id], 10)

    print("=> test console_window")
    test_bar(main_window_controller.view.console_window.get_top_widget(), "CONSOLE")
    testing_utils.wait_for_gui()
    config_id = 'CONSOLE_DOCKED_POS'
    pane_id = constants.PANE_ID['CONSOLE_DOCKED_POS']
    print("check pos of ", config_id, pane_id)
    assert_pos_equality(main_window_controller.view[pane_id].get_position(), stored_pane_positions[config_id], 10)

    print("=> test left_bar_window")
    test_bar(main_window_controller.view.left_bar_window.get_top_widget(), "LEFT_BAR")
    testing_utils.wait_for_gui()
    config_id = 'LEFT_BAR_DOCKED_POS'
    pane_id = constants.PANE_ID['LEFT_BAR_DOCKED_POS']
    print("check pos of ", config_id, pane_id)
    assert_pos_equality(main_window_controller.view[pane_id].get_position(), stored_pane_positions[config_id], 10)

    # print "check if pane positions are still like in runtime_config.yaml"
    # for config_id, pane_id in constants.PANE_ID.items():
    #     print "check pos of ", config_id, pane_id
    #     assert_pos_equality(main_window_controller.view[pane_id].get_position(), stored_pane_positions[config_id], 95)


def test_window_positions(caplog):
    testing_utils.run_gui(core_config=None,
                          runtime_config={
                              'MAIN_WINDOW_MAXIMIZED': False,
                              'MAIN_WINDOW_SIZE': (1500, 800),
                              'MAIN_WINDOW_POS': (0, 0),
                              'LEFT_BAR_WINDOW_SIZE': (800, 800),
                              'RIGHT_BAR_WINDOW_SIZE': (800, 800),
                              'CONSOLE_WINDOW_SIZE': (800, 800),
                              'LEFT_BAR_WINDOW_POS': (10, 10),
                              'RIGHT_BAR_WINDOW_POS': (10, 10),
                              'CONSOLE_WINDOW_POS': (10, 10),
                              'LEFT_BAR_HIDDEN': False,
                              'RIGHT_BAR_HIDDEN': False,
                              'CONSOLE_HIDDEN': False,
                              'LEFT_BAR_WINDOW_UNDOCKED': False,
                              'RIGHT_BAR_WINDOW_UNDOCKED': False,
                              'CONSOLE_WINDOW_UNDOCKED': False
                          },
                          gui_config={'HISTORY_ENABLED': False, 'AUTO_BACKUP_ENABLED': False})
    from rafcon.gui.runtime_config import global_runtime_config
    original_runtime_config = global_runtime_config.as_dict()

    try:
        undock_sidebars()
    finally:
        for key, value in original_runtime_config.items():
            call_gui_callback(global_runtime_config.set_config_value, key, value)

        testing_utils.close_gui()
        testing_utils.shutdown_environment(caplog=caplog)


def test_pane_positions(caplog):
    testing_utils.run_gui(core_config=None,
                          gui_config={'HISTORY_ENABLED': False, 'AUTO_BACKUP_ENABLED': False},
                          runtime_config={
                              'MAIN_WINDOW_MAXIMIZED': False,
                              'MAIN_WINDOW_SIZE': (1500, 800),
                              'MAIN_WINDOW_POS': (0, 0),
                              'LEFT_BAR_DOCKED_POS': 400,
                              'RIGHT_BAR_DOCKED_POS': 800,
                              'CONSOLE_DOCKED_POS': 600,
                              'LEFT_BAR_WINDOW_UNDOCKED': False,
                              'RIGHT_BAR_WINDOW_UNDOCKED': False,
                              'CONSOLE_WINDOW_UNDOCKED': False,
                              'LEFT_BAR_HIDDEN': False,
                              'RIGHT_BAR_HIDDEN': False,
                              'CONSOLE_HIDDEN': False,
                          })
    from rafcon.gui.runtime_config import global_runtime_config
    original_runtime_config = global_runtime_config.as_dict()

    try:
        check_pane_positions()
    finally:
        for key, value in original_runtime_config.items():
            call_gui_callback(global_runtime_config.set_config_value, key, value)

        testing_utils.close_gui()
        testing_utils.shutdown_environment(caplog=caplog)


if __name__ == '__main__':
    test_window_positions(None)
    test_pane_positions(None)
    # pytest.main([__file__, '-xs'])
