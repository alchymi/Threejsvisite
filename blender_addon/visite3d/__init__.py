bl_info = {
    "name": "3D Visite",
    "author": "Jimmy Fischer",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > 3D Visite",
    "description": "Scene setup for Three.js FPS walkthrough — colliders, spawn point, texture optimization",
    "category": "3D View",
}

import bpy
from . import colliders
from . import textures


def register():
    colliders.register()
    textures.register()


def unregister():
    textures.unregister()
    colliders.unregister()
