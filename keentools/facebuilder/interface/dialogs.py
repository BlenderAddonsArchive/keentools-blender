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
import re

import bpy
from bpy.types import Operator

from ...addon_config import Config, get_operator
from ...facebuilder_config import FBConfig, get_fb_settings
from ..callbacks import mesh_update_accepted, mesh_update_canceled


class FB_OT_BlendshapesWarning(Operator):
    bl_idname = FBConfig.fb_blendshapes_warning_idname
    bl_label = 'Warning'
    bl_options = {'REGISTER', 'INTERNAL'}

    headnum: bpy.props.IntProperty(default=0)
    accept: bpy.props.BoolProperty(name='Change the topology and '
                                        'recreate blendshapes',
                                   default=False)
    content_red = []
    content_white = []

    def output_text(self, layout, content, red=False):
        for txt in content:
            row = layout.row()
            row.alert = red
            row.label(text=txt)

    def draw(self, context):
        layout = self.layout.column()

        col = layout.column()
        col.scale_y = Config.text_scale_y

        self.output_text(col, self.content_red, red=True)
        self.output_text(col, self.content_white, red=False)

        layout.prop(self, 'accept')

    def execute(self, context):
        if (self.accept):
            mesh_update_accepted(self.headnum)
        else:
            mesh_update_canceled(self.headnum)
        return {'FINISHED'}

    def cancel(self, context):
        mesh_update_canceled(self.headnum)

    def invoke(self, context, event):
        self.content_red = [
            'Your model has FaceBuilder FACS blendshapes attached to it.',
            'Once you change the topology, the blendshapes will be recreated.',
            'All modifications added to the standard blendshapes, ',
            'as well as all custom blendshapes are going to be lost.',
            ' ']
        self.content_white = [
            'If you have animated the model using old blendshapes, ',
            'the new ones will be linked to the same Action track,',
            'so you\'re not going to lose your animation.',
            'If you have deleted some of the standard FaceBuilder '
            'FACS blendshapes, ',
            'they\'re not going to be recreated again.',
            ' ',
            'We recommend saving a backup file before changing the topology.',
            ' ']
        return context.window_manager.invoke_props_dialog(self, width=400)


class FB_OT_NoBlendshapesUntilExpressionWarning(Operator):
    bl_idname = FBConfig.fb_noblenshapes_until_expression_warning_idname
    bl_label = 'Blendshapes can\'t be created'
    bl_options = {'REGISTER', 'INTERNAL'}

    headnum: bpy.props.IntProperty(default=0)
    accept: bpy.props.BoolProperty(name='Set neutral expression',
                                   default=False)
    content_red = []

    def output_text(self, layout, content, red=False):
        for txt in content:
            row = layout.row()
            row.alert = red
            row.label(text=txt)

    def draw(self, context):
        layout = self.layout.column()
        col = layout.column()
        col.scale_y = Config.text_scale_y
        self.output_text(col, self.content_red, red=True)
        layout.prop(self, 'accept')

    def execute(self, context):
        if (self.accept):
            settings = get_fb_settings()
            head = settings.get_head(self.headnum)
            if head is None:
                return {'CANCELLED'}

            head.set_neutral_expression_view()
            op = get_operator(FBConfig.fb_create_blendshapes_idname)
            op('EXEC_DEFAULT')

        return {'FINISHED'}

    def cancel(self, context):
        pass

    def invoke(self, context, event):
        self.content_red = [
            'Unfortunately, expressions extracted from photos ',
            'can\'t be mixed with FACS blendshapes. ',
            'You need a neutral expression in order to create FACS blendshapes.',
            ' ']

        return context.window_manager.invoke_props_dialog(self, width=400)


class FB_OT_TexSelector(Operator):
    bl_idname = FBConfig.fb_tex_selector_idname
    bl_label = "Select images:"
    bl_description = "Create texture using pinned views"
    bl_options = {'REGISTER', 'INTERNAL'}

    headnum: bpy.props.IntProperty(default=0)

    def draw(self, context):
        settings = get_fb_settings()
        head = settings.get_head(self.headnum)
        layout = self.layout

        if not head.has_cameras():
            layout.label(text="You need at least one image to create texture.",
                         icon='ERROR')
            return

        box = layout.box()
        checked_views = False
        for camera in head.cameras:
            row = box.row()
            if camera.has_pins():
                row.prop(camera, 'use_in_tex_baking', text='')
                if camera.use_in_tex_baking:
                    checked_views = True
            else:
                row.active = False
                row.label(text='', icon='CHECKBOX_DEHLT')

            image_icon = 'PINNED' if camera.has_pins() else 'FILE_IMAGE'
            if camera.cam_image:
                row.label(text=camera.get_image_name(), icon=image_icon)
            else:
                row.label(text='-- empty --', icon='LIBRARY_DATA_BROKEN')

        row = box.row()

        op = row.operator(FBConfig.fb_filter_cameras_idname, text='All')
        op.action = 'select_all_cameras'
        op.headnum = self.headnum

        op = row.operator(FBConfig.fb_filter_cameras_idname, text='None')
        op.action = 'deselect_all_cameras'
        op.headnum = self.headnum

        col = layout.column()
        col.scale_y = Config.text_scale_y

        if checked_views:
            col.label(text="Please note: texture creation is very "
                           "time consuming.")
        else:
            col.alert = True
            col.label(text="You need to select at least one image "
                           "to create texture.")

        layout.prop(settings, 'tex_auto_preview')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        logger = logging.getLogger(__name__)
        logger.debug('START TEXTURE CREATION')

        head = get_fb_settings().get_head(self.headnum)
        if head is None:
            logger.error('WRONG HEADNUM')
            return {'CANCELLED'}

        if head.has_cameras():
            op = get_operator(FBConfig.fb_bake_tex_idname)
            res = op('INVOKE_DEFAULT', headnum=self.headnum)

            if res == {'CANCELLED'}:
                logger.debug('CANNOT CREATE TEXTURE')
                self.report({'ERROR'}, "Can't create texture")
            elif res == {'FINISHED'}:
                logger.debug('TEXTURE CREATED')
                self.report({'INFO'}, "Texture has been created successfully")

        return {'FINISHED'}
