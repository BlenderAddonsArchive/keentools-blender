# ##### BEGIN GPL LICENSE BLOCK #####
# KeenTools for blender is a blender addon for using KeenTools in Blender.
# Copyright (C) 2019  KeenTools

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ##### END GPL LICENSE BLOCK #####

import logging
from threading import Lock
from collections import namedtuple
from enum import IntEnum
from datetime import datetime, timedelta

import bpy

from ..config import get_operator, get_main_settings, Config, ErrorType
from ..blender_independent_packages.pykeentools_loader import (
    module as pkt_module, is_installed as pkt_is_installed,
    updates_downloaded, download_zips_async, remove_downloaded_zips,
    install_downloaded_zips)

from ..utils.html import parse_html, skip_new_lines_and_spaces, render_main
from ..utils.other import force_ui_redraw


def mock_response():
    response = lambda: None
    response.description_url = 'https://keentools.io/downloads'
    response.download_url = 'https://keentools.io/downloads'
    response.message = "<h3>What's New in KeenTools 2021.2.1</h3>\n" \
                       "<ul>\n  " \
                       "<li>fixed performance issues in Nuke 12;</li>\n  " \
                       "<li>pintooling performance improvements;</li>\n  " \
                       "<li>fixed large frame numbers bug;</li>\n  " \
                       "<li>fixed invisible model in macOS Catalina;</li>\n " \
                       "<li>minor fixes and improvements</li>\n" \
                       "</ul>\n<br />\n"
    response.plugin_name = 'FaceBuilder'
    try:
        response.version = pkt_module().Version(2021, 2, 1)
    except Exception:
        response.version = None
    return response


def _version_to_tuple(version):
    if type(version).__name__ == 'str':
        if version == "":
            return tuple([0, 0, 0])
        return tuple(map(int, version.split('.')))
    if type(version).__name__ == 'Version':
        return tuple([version.major, version.minor, version.patch])
    return version


def _downloaded_version():
    settings = get_main_settings()
    return settings.preferences().downloaded_version


def _latest_installation_skip_version():
    settings = get_main_settings()
    return settings.preferences().latest_installation_skip_version


_PREFERENCES_DATETIME_FORMAT = '%d/%m/%y %H:%M:%S'


def _operator_available_time(previous_show_datetime_str):
    if previous_show_datetime_str == '':
        return True
    previous_show_time = datetime.strptime(previous_show_datetime_str, _PREFERENCES_DATETIME_FORMAT)
    return (datetime.now() - previous_show_time).total_seconds() // 3600 >= 24


def render_active_message(layout):
    settings = get_main_settings()
    updater_state = settings.preferences().updater_state
    limit = 64
    if updater_state == UpdateState.UPDATES_AVAILABLE:
        FBUpdater.render_message(layout, limit=limit)
    elif updater_state == UpdateState.DOWNLOADING:
        FBDownloadNotification.render_message(layout, limit=limit)
    elif updater_state == UpdateState.INSTALL:
        FBInstallationReminder.render_message(layout, limit=limit)


def preferences_current_active_updater_operator_info():
    settings = get_main_settings()
    updater_state = settings.preferences().updater_state
    OperatorInfo = namedtuple('OperatorInfo', 'idname, text, icon')
    if updater_state == UpdateState.UPDATES_AVAILABLE:
        return OperatorInfo(Config.fb_download_the_update_idname, 'Download the update', 'IMPORT')
    elif updater_state == UpdateState.INSTALL:
        return OperatorInfo(Config.fb_install_updates_idname, 'Update and restart blender', 'FILE_REFRESH')
    else:
        return None


class UpdateState(IntEnum):
    INITIAL = 1
    UPDATES_AVAILABLE = 2
    DOWNLOADING = 3
    INSTALL = 4


class CurrentStateExecutor:
    _panel_updater_state = UpdateState.INITIAL

    @classmethod
    def set_current_panel_updater_state(cls, state, set_preferences_updater_state=True):
        cls._panel_updater_state = state
        if set_preferences_updater_state:
            settings = get_main_settings()
            settings.preferences().updater_state = state

    @classmethod
    def compute_current_panel_updater_state(cls):
        downloaded_version = _version_to_tuple(_downloaded_version())
        if cls._panel_updater_state == UpdateState.INITIAL:
            if FBUpdater.is_available():
                cls.set_current_panel_updater_state(UpdateState.UPDATES_AVAILABLE)
            elif downloaded_version > _version_to_tuple(Config.addon_version) and \
                    downloaded_version != _version_to_tuple(_latest_installation_skip_version()) and \
                    updates_downloaded() and FBInstallationReminder.is_available():
                cls.set_current_panel_updater_state(UpdateState.INSTALL)
        elif cls._panel_updater_state == UpdateState.INSTALL:
            if FBUpdater.is_available():
                cls.set_current_panel_updater_state(UpdateState.UPDATES_AVAILABLE)
        return cls._panel_updater_state


class FBUpdater:
    _response = None
    _response = mock_response()  # Mock for testing (1/3)
    _parsed_response_content = None

    @classmethod
    def is_available(cls):
        settings = get_main_settings()
        previous_show_time_str = settings.preferences().latest_show_datetime_update_reminder
        latest_skip_version = settings.preferences().latest_update_skip_version
        return _operator_available_time(previous_show_time_str) and cls.has_response() and \
               _version_to_tuple(_downloaded_version()) < _version_to_tuple(cls.version()) and \
               _version_to_tuple(latest_skip_version) != _version_to_tuple(cls.version())

    @classmethod
    def is_active(cls):
        return CurrentStateExecutor.compute_current_panel_updater_state() == UpdateState.UPDATES_AVAILABLE

    @classmethod
    def has_response(cls):
        return cls.get_response() is not None

    @classmethod
    def has_response_message(cls):
        return cls._parsed_response_content is not None

    @classmethod
    def set_response(cls, val):
        cls._response = val

    @classmethod
    def get_response(cls):
        if cls._response is not None and cls._response.version is None:
            cls._response = mock_response()  # Mock for testing (2/3)
        return cls._response

    @classmethod
    def get_parsed(cls):
        return cls._parsed_response_content

    @classmethod
    def set_parsed(cls, val):
        cls._parsed_response_content = val

    @classmethod
    def clear_message(cls):
        cls.set_response(None)
        cls.set_parsed(None)

    @classmethod
    def render_message(cls, layout, limit=32):
        parsed = cls.get_parsed()
        if parsed is not None:
            render_main(layout, parsed, limit)

    @classmethod
    def get_update_checker(cls):
        pykeentools = pkt_module()
        platform = 'Blender'
        ver = pykeentools.Version(*bpy.app.version)
        uc = pykeentools.UpdatesChecker.instance(platform, ver)
        return uc

    @classmethod
    def remind_later(cls):
        settings = get_main_settings()
        settings.preferences().latest_show_datetime_update_reminder = \
            datetime.now().strftime(_PREFERENCES_DATETIME_FORMAT)

    @classmethod
    def version(cls):
        return cls.get_response().version

    @classmethod
    def init_updater(cls):
        if cls.has_response_message() or not pkt_is_installed():
            return

        uc = cls.get_update_checker()
        res = uc.check_for_updates('FaceBuilder')
        res = cls.get_response()  # Mock for testing (3/3)
        if res is not None:
            cls.set_response(res)
            parsed = parse_html(skip_new_lines_and_spaces(res.message))
            cls.set_parsed(parsed)


class DownloadedPartsExecutor:
    _state_mutex = Lock()
    _downloaded_parts = 0

    @classmethod
    def get_downloaded_parts_count(cls):
        cls._state_mutex.acquire()
        try:
            return cls._downloaded_parts
        finally:
            cls._state_mutex.release()

    @classmethod
    def inc_downloaded_parts_count(cls):
        cls._state_mutex.acquire()
        try:
            cls._downloaded_parts += 1
        finally:
            cls._state_mutex.release()

    @classmethod
    def nullify_downloaded_parts_count(cls):
        cls._state_mutex.acquire()
        try:
            cls._downloaded_parts = 0
        finally:
            cls._state_mutex.release()


def _set_installing():
    DownloadedPartsExecutor.inc_downloaded_parts_count()
    if DownloadedPartsExecutor.get_downloaded_parts_count() == 2:
        settings = get_main_settings()
        settings.preferences().downloaded_version = str(FBUpdater.version())
        CurrentStateExecutor.set_current_panel_updater_state(UpdateState.INSTALL)
        force_ui_redraw('VIEW_3D')
        force_ui_redraw('PREFERENCES')


class FB_OT_DownloadTheUpdate(bpy.types.Operator):
    bl_idname = Config.fb_download_the_update_idname
    bl_label = 'Download the update'
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_description = 'Download the latest version of addon and core'

    def execute(self, context):
        CurrentStateExecutor.set_current_panel_updater_state(UpdateState.DOWNLOADING)
        DownloadedPartsExecutor.nullify_downloaded_parts_count()
        download_zips_async(final_callback=_set_installing)
        return {'FINISHED'}


class FB_OT_RemindLater(bpy.types.Operator):
    bl_idname = Config.fb_remind_later_idname
    bl_label = 'Remind later'
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_description = 'Remind about this update tomorrow'

    def execute(self, context):
        CurrentStateExecutor.set_current_panel_updater_state(UpdateState.INITIAL,
                                                             set_preferences_updater_state=False)
        logger = logging.getLogger(__name__)
        logger.debug('REMIND LATER')
        FBUpdater.remind_later()
        return {'FINISHED'}


class FB_OT_SkipVersion(bpy.types.Operator):
    bl_idname = Config.fb_skip_version_idname
    bl_label = 'Skip this version'
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_description = 'Skip this version'

    def execute(self, context):
        CurrentStateExecutor.set_current_panel_updater_state(UpdateState.INITIAL,
                                                             set_preferences_updater_state=False)
        logger = logging.getLogger(__name__)
        logger.debug('SKIP THIS VERSION')
        settings = get_main_settings()
        settings.preferences().latest_update_skip_version = str(FBUpdater.version())
        return {'FINISHED'}


class FBDownloadNotification:
    @classmethod
    def is_active(cls):
        return CurrentStateExecutor.compute_current_panel_updater_state() == UpdateState.DOWNLOADING

    @classmethod
    def render_message(cls, layout, limit=32):
        _message_text = '<h3>Updates are downloading.</h3>' \
                        '<h3>We will let you know when they are ready for installation.</h3>'
        if cls.is_active():
            render_main(layout, parse_html(_message_text), limit)


class FBInstallationReminder:
    @classmethod
    def is_active(cls):
        return CurrentStateExecutor.compute_current_panel_updater_state() == UpdateState.INSTALL

    @classmethod
    def is_available(cls):
        settings = get_main_settings()
        previous_show_time_str = settings.preferences().latest_show_datetime_installation_reminder
        return _operator_available_time(previous_show_time_str)

    @classmethod
    def render_message(cls, layout, limit=32):
        _message_text = 'The update {} is ready to be installed.' \
                        'Blender will be relaunched after installing the update automatically.' \
                        'Please save your project before continuing. Proceed?'. \
            format(_downloaded_version())
        render_main(layout, parse_html(_message_text), limit)

    @classmethod
    def remind_later(cls):
        settings = get_main_settings()
        settings.preferences().latest_show_datetime_installation_reminder = \
            datetime.now().strftime(_PREFERENCES_DATETIME_FORMAT)


def _start_new_blender(cmd_line):
    import platform
    import os
    import subprocess
    install_downloaded_zips(True)
    if platform.system() == 'Linux':
        new_ref = os.fork()
        if new_ref == 0:
            subprocess.call([cmd_line])
    else:
        subprocess.call([cmd_line])


def _clear_updater_info():
    from ..preferences import reset_updater_preferences_to_default
    reset_updater_preferences_to_default()


class FB_OT_InstallUpdates(bpy.types.Operator):
    bl_idname = Config.fb_install_updates_idname
    bl_label = 'The blender will restart, save your changes before'
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_description = 'Install updates and restart blender'

    def execute(self, context):
        if not bpy.data.is_dirty:
            if not updates_downloaded():
                warn = get_operator(Config.fb_warning_idname)
                warn('INVOKE_DEFAULT', msg=ErrorType.DownloadingProblem)
                _clear_updater_info()
                CurrentStateExecutor.compute_current_panel_updater_state()
                force_ui_redraw('VIEW_3D')
                force_ui_redraw('PREFERENCES')
                return {'CANCELLED'}
            CurrentStateExecutor.set_current_panel_updater_state(UpdateState.INITIAL)
            import sys
            import atexit
            atexit.register(_start_new_blender, sys.argv[0])
            bpy.ops.wm.quit_blender()
        return {'FINISHED'}

    def invoke(self, context, event):
        if bpy.data.is_dirty:
            return context.window_manager.invoke_props_dialog(self, width=300)
        return self.execute(context)


class FB_OT_RemindInstallLater(bpy.types.Operator):
    bl_idname = Config.fb_remind_install_later_idname
    bl_label = 'Remind install tommorow'
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_description = 'Remind install tommorow'

    def execute(self, context):
        CurrentStateExecutor.set_current_panel_updater_state(UpdateState.INITIAL,
                                                             set_preferences_updater_state=False)
        FBInstallationReminder.remind_later()
        return {'FINISHED'}


class FB_OT_SkipInstallation(bpy.types.Operator):
    bl_idname = Config.fb_skip_installation_idname
    bl_label = 'Skip installation'
    bl_options = {'REGISTER', 'INTERNAL'}
    bl_description = 'Skip installation'

    def execute(self, context):
        CurrentStateExecutor.set_current_panel_updater_state(UpdateState.INITIAL,
                                                             set_preferences_updater_state=False)
        settings = get_main_settings()
        settings.preferences().latest_installation_skip_version = settings.preferences().downloaded_version
        return {'FINISHED'}
