# ##### BEGIN GPL LICENSE BLOCK #####
# KeenTools for blender is a blender addon for using KeenTools in Blender.
# Copyright (C) 2022 KeenTools

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

import bpy

from ..geotracker_config import GTConfig, get_current_geotracker_item
from .utils.geotracker_acts import (add_keyframe_act,
                                    fit_render_size_act,
                                    fit_time_length_act,
                                    remove_focal_keyframe_act,
                                    remove_focal_keyframes_act,
                                    bake_texture_from_frames_act)
from .utils.precalc import precalc_with_runner_act
from ..utils.bpy_common import bpy_current_frame


class GT_OT_Actor(bpy.types.Operator):
    bl_idname = GTConfig.gt_actor_idname
    bl_label = 'Actor Operator'
    bl_options = {'REGISTER'}

    action: bpy.props.StringProperty(name='Action string', default='none')
    num: bpy.props.IntProperty(name='Numeric parameter', default=0)

    def draw(self, context):
        pass

    def execute(self, context):
        logger = logging.getLogger(__name__)
        logger.debug('ACTION call: {}'.format(self.action))

        if self.action == 'add_keyframe':
            act_status = add_keyframe_act()
            if not act_status.success:
                self.report({'ERROR'}, act_status.error_message)
                return {'CANCELLED'}

            self.report({'INFO'}, self.action)
            return {'FINISHED'}

        elif self.action == 'create_precalc':
            status, msg = precalc_with_runner_act(context)
            if not status:
                self.report({'ERROR'}, msg)
            return {'FINISHED'}

        elif self.action == 'fit_render_size':
            act_status = fit_render_size_act()
            if not act_status.success:
                self.report({'ERROR'}, act_status.error_message)
            else:
                self.report({'INFO'}, act_status.error_message)
            return {'FINISHED'}

        elif self.action == 'fit_time_length':
            act_status = fit_time_length_act()
            if not act_status.success:
                self.report({'ERROR'}, act_status.error_message)
            else:
                self.report({'INFO'}, act_status.error_message)
            return {'FINISHED'}

        elif self.action == 'remove_focal_keyframe':
            act_status = remove_focal_keyframe_act()
            if not act_status.success:
                self.report({'ERROR'}, act_status.error_message)
            else:
                self.report({'INFO'}, act_status.error_message)
            return {'FINISHED'}

        elif self.action == 'remove_focal_keyframes':
            act_status = remove_focal_keyframes_act()
            if not act_status.success:
                self.report({'ERROR'}, act_status.error_message)
            else:
                self.report({'INFO'}, act_status.error_message)
            return {'FINISHED'}

        elif self.action == 'reproject_frame':
            act_status = bake_texture_from_frames_act([bpy_current_frame()])
            if not act_status.success:
                self.report({'ERROR'}, act_status.error_message)
            else:
                self.report({'INFO'}, act_status.error_message)
            return {'FINISHED'}

        elif self.action == 'select_all_frames':
            geotracker = get_current_geotracker_item()
            if not geotracker:
                return {'CANCELLED'}
            for item in geotracker.selected_frames:
                item.selected = True
            return {'FINISHED'}

        elif self.action == 'deselect_all_frames':
            geotracker = get_current_geotracker_item()
            if not geotracker:
                return {'CANCELLED'}
            for item in geotracker.selected_frames:
                item.selected = False
            return {'FINISHED'}

        self.report({'INFO'}, self.action)
        return {'FINISHED'}
