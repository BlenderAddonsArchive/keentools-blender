# ##### BEGIN GPL LICENSE BLOCK #####
# KeenTools for blender is a blender addon for using KeenTools in Blender.
# Copyright (C) 2022-2023 KeenTools

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

from typing import Any

from ..utils.kt_logging import KTLogger
from ..facetracker_config import get_ft_settings
from ..tracker.cam_input import (CameraInput,
                                 GeoInput,
                                 ImageInput,
                                 Mask2DInput,
                                 GeoTrackerResultsStorage)


_log = KTLogger(__name__)


class FTCameraInput(CameraInput):
    @classmethod
    def get_settings(cls) -> Any:
        return get_ft_settings()


class FTGeoInput(GeoInput):
    @classmethod
    def get_settings(cls) -> Any:
        return get_ft_settings()


class FTImageInput(ImageInput):
    @classmethod
    def get_settings(cls) -> Any:
        return get_ft_settings()


class FTMask2DInput(Mask2DInput):
    @classmethod
    def get_settings(cls) -> Any:
        return get_ft_settings()


class FTGeoTrackerResultsStorage(GeoTrackerResultsStorage):
    @classmethod
    def get_settings(cls) -> Any:
        return get_ft_settings()
