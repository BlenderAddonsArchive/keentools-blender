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

import math
import bpy
import numpy as np
import logging
import os

from ..config import Config
from ..utils.rig_slider import create_slider, create_rectangle, create_label
from ..utils.coords import (xy_to_xz_rotation_matrix_3x3,
                            xz_to_xy_rotation_matrix_3x3)
import keentools_facebuilder.blender_independent_packages.pykeentools_loader as pkt


def _has_no_blendshapes(obj):
    return not obj.data.shape_keys


def has_blendshapes_action(obj):
    return obj.data.shape_keys and obj.data.shape_keys.animation_data and \
           obj.data.shape_keys.animation_data.action


def _create_basis_blendshape(obj):
    if _has_no_blendshapes(obj):
        obj.shape_key_add(name='Basis')


def _get_all_blendshape_names(obj):
    if _has_no_blendshapes(obj):
        return []
    res = [kb.name for kb in obj.data.shape_keys.key_blocks]
    return res[1:]


def _get_safe_blendshapes_action(
        obj, action_name=Config.default_blendshapes_action_name):
    if _has_no_blendshapes(obj):
        return None
    animation_data = obj.data.shape_keys.animation_data
    if not animation_data:
        animation_data = obj.data.shape_keys.animation_data_create()
        if not animation_data:
            return None
    if not animation_data.action:
        animation_data.action = \
            bpy.data.actions.new(action_name)
    return animation_data.action


def _extend_scene_timeline(keyframe_num):
    scene = bpy.context.scene
    if scene.frame_end < keyframe_num:
        scene.frame_end = keyframe_num


def _get_action_fcurve(action, data_path, index=0):
    return action.fcurves.find(data_path, index=index)


def _get_safe_action_fcurve(action, data_path, index=0):
    fcurve = _get_action_fcurve(action, data_path, index=index)
    if fcurve:
        return fcurve
    return action.fcurves.new(data_path, index=index)


def _get_fcurve_data(fcurve):
    if not fcurve:
        return []
    return [p.co for p in fcurve.keyframe_points]


def _clear_fcurve(fcurve):
    for p in reversed(fcurve.keyframe_points):
        fcurve.keyframe_points.remove(p)


def _put_anim_data_in_fcurve(fcurve, anim_data):
    if not fcurve:
        return
    start_index = len(fcurve.keyframe_points)
    fcurve.keyframe_points.add(len(anim_data))
    for i, point in enumerate(anim_data):
        fcurve.keyframe_points[start_index + i].co = point
    fcurve.update()


def remove_blendshapes(obj):
    if _has_no_blendshapes(obj):
        return
    for blendshape in reversed([kb for kb in obj.data.shape_keys.key_blocks]):
        obj.shape_key_remove(blendshape)


def disconnect_blendshapes_action(obj):
    if has_blendshapes_action(obj):
        action = obj.data.shape_keys.animation_data.action
        obj.data.shape_keys.animation_data.action = None
        obj.data.update()
        return action
    return None


def zero_all_blendshape_weights(obj):
    if _has_no_blendshapes(obj):
        return -1
    counter = 0
    for kb in obj.data.shape_keys.key_blocks[1:]:
        kb.value = 0
        counter += 1
    return counter


def _get_pykeentools_geo_from_mesh(obj):
    mesh = obj.data
    verts = np.empty((len(mesh.vertices), 3), dtype=np.float32)
    mesh.vertices.foreach_get('co', np.reshape(verts, len(mesh.vertices) * 3))

    mb = pkt.module().MeshBuilder()
    mb.add_points(verts @ xz_to_xy_rotation_matrix_3x3())
    me = mb.mesh()
    geo = pkt.module().Geo()
    geo.add_mesh(me)
    return geo


def _get_facs_executor(obj, scale):
    logger = logging.getLogger(__name__)
    model = _get_pykeentools_geo_from_mesh(obj)

    try:
        fe = pkt.module().FacsExecutor(model, scale)
    except pkt.module().FacsLoadingException:
        logger.error('CANNOT_LOAD_FACS: FacsLoadingException')
        return None
    except Exception as error:
        logger.error('CANNOT_LOAD_FACS: Unknown Exception')
        logger.error('info: {} -- {}'.format(type(error), error))
        return None
    if not fe.facs_enabled():
        logger.error('CANNOT_LOAD_FACS: FACS are not enabled')
        return None
    return fe


def _update_blendshape_verts(shape, verts):
    shape.data.foreach_set(
        'co', (verts @ xy_to_xz_rotation_matrix_3x3()).ravel())


def create_facs_blendshapes(obj, scale):
    facs_executor = _get_facs_executor(obj, scale)
    if not facs_executor:
        return -1

    _create_basis_blendshape(obj)
    counter = 0
    for i, name in enumerate(facs_executor.facs_names):
        if obj.data.shape_keys.key_blocks.find(name) < 0:
            shape = obj.shape_key_add(name=name)
            verts = facs_executor.get_facs_blendshape(i)
            _update_blendshape_verts(shape, verts)
            counter += 1
    return counter


def update_facs_blendshapes(obj, scale):
    assert not _has_no_blendshapes(obj)
    facs_executor = _get_facs_executor(obj, scale)
    if not facs_executor:
        return -1

    counter = 0
    for i, name in enumerate(facs_executor.facs_names):
        index = obj.data.shape_keys.key_blocks.find(name)
        if index >= 0:
            shape = obj.data.shape_keys.key_blocks[index]
            verts = facs_executor.get_facs_blendshape(i)
            _update_blendshape_verts(shape, verts)
            counter += 1
    obj.data.update()
    return counter


def restore_facs_blendshapes(obj, scale, restore_names):
    _create_basis_blendshape(obj)
    facs_executor = _get_facs_executor(obj, scale)
    if not facs_executor:
        return -1

    counter = 0
    for i, name in enumerate(facs_executor.facs_names):
        if obj.data.shape_keys.key_blocks.find(name) < 0 \
                and (name in restore_names):
            shape = obj.shape_key_add(name=name)
            verts = facs_executor.get_facs_blendshape(i)
            _update_blendshape_verts(shape, verts)
            counter += 1
    obj.data.update()
    return counter


def load_csv_animation_to_blendshapes(obj, filepath):
    logger = logging.getLogger(__name__)
    try:
        fan = pkt.module().FacsAnimation()
        read_facs, ignored_columns = fan.load_from_csv_file(filepath)
        facs_names = pkt.module().FacsExecutor.facs_names
    except pkt.module().FacsLoadingException as err:
        logger.error('CANNOT_LOAD_CSV_ANIMATION: {}'.format(err))
        return {'status': False, 'message': str(err),
                'ignored': [], 'read_facs': []}
    except Exception as err:
        logger.error('CANNOT_LOAD_CSV_ANIMATION!: {} {}'.format(type(err), err))
        return {'status': False, 'message': str(err),
                'ignored': [], 'read_facs': []}

    action_name = os.path.splitext(os.path.basename(filepath))[0]
    blendshapes_action = _get_safe_blendshapes_action(obj, action_name)

    scene = bpy.context.scene
    fps = scene.render.fps
    start = scene.frame_current
    if not fan.timecodes_enabled():
        fps = 1
    keyframes = [start + x * fps for x in fan.keyframes()]
    for name in facs_names:
        blendshape_fcurve = _get_safe_action_fcurve(
            blendshapes_action, 'key_blocks["{}"].value'.format(name), index=0)
        animation = fan.at_name(name)
        anim_data = [x for x in zip(keyframes, animation)]
        _put_anim_data_in_fcurve(blendshape_fcurve, anim_data)
    obj.data.update()
    if len(keyframes) > 0:
        _extend_scene_timeline(keyframes[-1])

    logger.info('FACS CSV-Animation file: {}'.format(filepath))
    logger.info('Timecodes enabled: {}'.format(fan.timecodes_enabled()))
    if len(ignored_columns) > 0:
        logger.info('Ignored columns: {}'.format(ignored_columns))
    if len(read_facs) > 0:
        logger.info('Read facs: {}'.format(read_facs))
    return {'status': True, 'message': 'ok',
            'ignored': ignored_columns, 'read_facs': read_facs}


def create_facs_test_animation_on_blendshapes(obj, start_time=1, dtime=4):
    if _has_no_blendshapes(obj):
        return -1
    counter = 0
    blendshapes_action = _get_safe_blendshapes_action(
        obj, Config.example_animation_action_name)
    time = start_time
    for kb in obj.data.shape_keys.key_blocks[1:]:
        blendshape_fcurve = _get_safe_action_fcurve(
            blendshapes_action,
            'key_blocks["{}"].value'.format(kb.name),
            index=0)
        anim_data = [(time, 0.0), (time + dtime, 1.0), (time + 2 * dtime, 0)]
        time += dtime * 2
        _put_anim_data_in_fcurve(blendshape_fcurve, anim_data)
        counter += 1
    obj.data.update()
    _extend_scene_timeline(time)
    return counter


def _create_driver(target, control_obj, driver_name, control_prop='location.x'):
    res = target.driver_add('value')
    res.driver.type = 'AVERAGE'
    drv_var = res.driver.variables.new()
    drv_var.name = driver_name
    drv_var.type = 'SINGLE_PROP'
    drv_var.targets[0].id = control_obj
    drv_var.targets[0].data_path = control_prop
    return res


def create_blendshape_controls(obj):
    if _has_no_blendshapes(obj):
        return {}
    blendshape_names = _get_all_blendshape_names(obj)
    controls = {}
    for name in blendshape_names:
        slider_dict = create_slider(name, name, width=1.0, height=0.2)
        driver = _create_driver(obj.data.shape_keys.key_blocks[name],
                                slider_dict['slider'],
                                Config.default_driver_name, 'location.x')
        controls[name] = {'control': slider_dict, 'driver': driver}
    return controls


def make_control_panel(controls_dict):
    count = len(controls_dict)
    columns_count = 4
    max_in_column = (count + columns_count - 1) // columns_count

    width = 1.0
    height = 0.2

    step_x = width * 2
    step_y = height * 2.4
    panel_width = step_x * columns_count
    panel_height = step_y * (max_in_column + 1)

    start_x = width * 0.5
    start_y = 0.5 * panel_height - 2 * height

    name = 'ControlPanel'
    main_rect = create_rectangle(name, panel_width, panel_height)
    label = create_label(name, label='Blendshape controls', size=2 * height)
    label.parent = main_rect
    label.location = (0, 0.5 * panel_height + 0.5 * height, 0)

    i = 0
    j = 0
    for name in controls_dict:
        rect = controls_dict[name]['control']['rectangle']
        rect.parent = main_rect
        rect.location = (start_x + j * step_x, start_y - i * step_y, 0)
        rect.hide_select = True
        i += 1
        if (i >= max_in_column):
            j += 1
            i = 0

    return main_rect


def remove_blendshape_drivers(obj):
    all_dict = _get_blendshapes_drivers(obj)
    for name in all_dict:
        obj.data.shape_keys.animation_data.drivers.remove(all_dict[name]['driver'])


def _find_all_children(obj, obj_list):
    for child in obj.children:
        _find_all_children(child, obj_list)
    obj_list.append(obj)


def delete_with_children(obj):
    arr = []
    _find_all_children(obj, arr)
    if arr:
        bpy.ops.object.delete({'selected_objects': arr})


def select_control_panel_sliders(panel_obj):
    arr = []
    _find_all_children(panel_obj, arr)
    empties = [obj for obj in arr if obj.type == 'EMPTY']
    counter = 0
    if empties:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in empties:
            obj.select_set(state=True)
            counter += 1
    return counter


def _get_blendshapes_drivers(obj):
    if _has_no_blendshapes(obj):
        return {}
    drivers_dict = {}
    for drv in obj.data.shape_keys.animation_data.drivers:
        blendshape_name = drv.data_path.split('"')[1]
        drivers_dict[blendshape_name] = {
            'driver': drv, 'slider': drv.driver.variables[0].targets[0].id}
    return drivers_dict


def get_control_panel_by_drivers(obj):
    drivers_dict = _get_blendshapes_drivers(obj)
    if len(drivers_dict) == 0:
        return None
    name = [*drivers_dict.keys()][0]
    rect = drivers_dict[name]['slider'].parent
    if not rect:
        return None
    return rect.parent


def convert_controls_animation_to_blendshapes(obj):
    if _has_no_blendshapes(obj):
        return False
    all_dict = _get_blendshapes_drivers(obj)
    blend_action = _get_safe_blendshapes_action(obj)
    if not blend_action:
        return False
    for name in all_dict:
        item = all_dict[name]
        control_action = item['slider'].animation_data.action
        control_fcurve = _get_action_fcurve(control_action, 'location', index=0)
        anim_data = _get_fcurve_data(control_fcurve)
        blendshape_fcurve = _get_safe_action_fcurve(
            blend_action, 'key_blocks["{}"].value'.format(name), index=0)
        _clear_fcurve(blendshape_fcurve)
        _put_anim_data_in_fcurve(blendshape_fcurve, anim_data)
    return True


def convert_blendshapes_animation_to_controls(obj):
    if _has_no_blendshapes(obj):
        return False
    all_dict = _get_blendshapes_drivers(obj)
    blend_action = _get_safe_blendshapes_action(obj)
    if not blend_action:
        return False
    for name in all_dict:
        blendshape_fcurve = _get_action_fcurve(
            blend_action, 'key_blocks["{}"].value'.format(name), index=0)
        if not blendshape_fcurve:
            continue
        anim_data = _get_fcurve_data(blendshape_fcurve)

        item = all_dict[name]
        if not item['slider'].animation_data:
            item['slider'].animation_data_create()
        if not item['slider'].animation_data.action:
            item['slider'].animation_data.action = bpy.data.actions.new(name + 'Action')
        control_action = item['slider'].animation_data.action
        control_fcurve = _get_safe_action_fcurve(control_action, 'location', index=0)
        _clear_fcurve(control_fcurve)
        _put_anim_data_in_fcurve(control_fcurve, anim_data)
    return True


def create_facs_test_animation_on_sliders(obj, start_time=1, dtime=4):
    if _has_no_blendshapes(obj):
        return False
    all_dict = _get_blendshapes_drivers(obj)
    time = start_time
    for name in all_dict:
        item = all_dict[name]
        if not item['slider'].animation_data:
            item['slider'].animation_data_create()
        if not item['slider'].animation_data.action:
            item['slider'].animation_data.action = bpy.data.actions.new(name + 'Action')
        control_action = item['slider'].animation_data.action
        control_fcurve = _get_safe_action_fcurve(control_action, 'location', index=0)
        anim_data = [(time, 0.0), (time + dtime, 1.0), (time + 2 * dtime, 0)]
        time += dtime * 2
        _put_anim_data_in_fcurve(control_fcurve, anim_data)
    return True
