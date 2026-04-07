# ============================================================
# 3D Visite — Blender Scene Setup Script
# ============================================================
# Usage:
#   1. Open your scene in Blender
#   2. Open this script in the Scripting tab
#   3. Use the buttons in the sidebar (N panel > 3D Visite)
#
# Workflow:
#   - Select objects and click "Add Collider" to mark them
#     as collidable (box, mesh, or invisible wall)
#   - Place the 3D cursor where you want the player to spawn,
#     then click "Set Spawn Point"
#   - Export as GLB with "Custom Properties" checked
# ============================================================

import bpy
from mathutils import Vector

# -----------------------------------------------------------
# Custom property helpers
# -----------------------------------------------------------

COLLIDER_TYPES = [
    ("box", "Box", "Bounding box collider — fast, good for walls/floors/crates"),
    ("mesh", "Mesh", "Trimesh collider — precise, heavier, for complex shapes"),
    ("none", "None", "Remove collider from this object"),
]

SPAWN_NAME = "SpawnPoint"


def set_collider(obj, collider_type):
    """Set or remove the 'collider' custom property."""
    if collider_type == "none":
        if "collider" in obj:
            del obj["collider"]
    else:
        obj["collider"] = collider_type


def get_collider(obj):
    return obj.get("collider", "")


# -----------------------------------------------------------
# Operators
# -----------------------------------------------------------

class VISITE3D_OT_AddCollider(bpy.types.Operator):
    bl_idname = "visite3d.add_collider"
    bl_label = "Set Collider"
    bl_description = "Set collider type on selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    collider_type: bpy.props.EnumProperty(
        name="Type",
        items=COLLIDER_TYPES,
        default="box",
    )

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                set_collider(obj, self.collider_type)
                count += 1

                # Add naming convention prefix (reliable GLB export)
                name = obj.name
                # Remove existing prefixes
                for prefix in ('COL_', 'BOX_'):
                    if name.upper().startswith(prefix):
                        name = name[4:]
                        break

                if self.collider_type == "box":
                    obj.name = f"BOX_{name}"
                    obj.color = (0.2, 0.8, 0.2, 0.6)  # green
                elif self.collider_type == "mesh":
                    obj.name = f"COL_{name}"
                    obj.color = (0.2, 0.4, 1.0, 0.6)  # blue
                else:
                    obj.color = (1, 1, 1, 1)  # reset

        self.report({'INFO'}, f"Collider '{self.collider_type}' set on {count} object(s)")
        return {'FINISHED'}


class VISITE3D_OT_AddInvisibleWall(bpy.types.Operator):
    bl_idname = "visite3d.add_invisible_wall"
    bl_label = "Make Invisible Wall"
    bl_description = "Mark selected objects as invisible colliders (won't render but will block)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                set_collider(obj, "box")
                obj["invisible"] = True
                obj.display_type = 'WIRE'
                obj.color = (1.0, 0.3, 0.1, 0.4)  # orange wire
                count += 1

        self.report({'INFO'}, f"{count} invisible wall(s) created")
        return {'FINISHED'}


class VISITE3D_OT_SetSpawnPoint(bpy.types.Operator):
    bl_idname = "visite3d.set_spawn_point"
    bl_label = "Set Spawn Point"
    bl_description = "Create or move the SpawnPoint empty at the 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cursor_loc = context.scene.cursor.location.copy()

        # Find or create SpawnPoint
        spawn = bpy.data.objects.get(SPAWN_NAME)
        if spawn is None:
            spawn = bpy.data.objects.new(SPAWN_NAME, None)
            context.collection.objects.link(spawn)
            spawn.empty_display_type = 'ARROWS'
            spawn.empty_display_size = 0.5

        spawn.location = cursor_loc
        spawn["type"] = "SpawnPoint"

        self.report({'INFO'}, f"SpawnPoint at {cursor_loc.x:.2f}, {cursor_loc.y:.2f}, {cursor_loc.z:.2f}")
        return {'FINISHED'}


class VISITE3D_OT_SelectColliders(bpy.types.Operator):
    bl_idname = "visite3d.select_colliders"
    bl_label = "Select All Colliders"
    bl_description = "Select all objects with a collider property"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        count = 0
        for obj in context.scene.objects:
            if get_collider(obj):
                obj.select_set(True)
                count += 1
        self.report({'INFO'}, f"{count} collider(s) selected")
        return {'FINISHED'}


class VISITE3D_OT_ShowStats(bpy.types.Operator):
    bl_idname = "visite3d.show_stats"
    bl_label = "Show Stats"
    bl_description = "Show collider stats for the scene"

    def execute(self, context):
        box_count = 0
        mesh_count = 0
        invis_count = 0
        has_spawn = bpy.data.objects.get(SPAWN_NAME) is not None

        for obj in context.scene.objects:
            c = get_collider(obj)
            if c == "box":
                box_count += 1
                if obj.get("invisible"):
                    invis_count += 1
            elif c == "mesh":
                mesh_count += 1

        self.report({'INFO'},
            f"Box: {box_count} ({invis_count} invisible) | Mesh: {mesh_count} | Spawn: {'Yes' if has_spawn else 'NO'}")
        return {'FINISHED'}


# -----------------------------------------------------------
# Panel
# -----------------------------------------------------------

class VISITE3D_PT_Panel(bpy.types.Panel):
    bl_label = "3D Visite"
    bl_idname = "VISITE3D_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "3D Visite"

    def draw(self, context):
        layout = self.layout

        # --- Colliders ---
        box = layout.box()
        box.label(text="Colliders", icon='MOD_PHYSICS')

        row = box.row(align=True)
        op = row.operator("visite3d.add_collider", text="Box", icon='MESH_CUBE')
        op.collider_type = "box"
        op = row.operator("visite3d.add_collider", text="Mesh", icon='MESH_ICOSPHERE')
        op.collider_type = "mesh"
        op = row.operator("visite3d.add_collider", text="Remove", icon='X')
        op.collider_type = "none"

        box.operator("visite3d.add_invisible_wall", icon='GHOST_ENABLED')
        box.operator("visite3d.select_colliders", icon='RESTRICT_SELECT_OFF')

        # Show collider info for active object
        obj = context.active_object
        if obj and obj.type == 'MESH':
            c = get_collider(obj)
            if c:
                box.label(text=f"Active: {obj.name} → {c}", icon='CHECKMARK')
            else:
                box.label(text=f"Active: {obj.name} → no collider", icon='DOT')

        # --- Spawn ---
        box2 = layout.box()
        box2.label(text="Spawn Point", icon='CURSOR')
        box2.operator("visite3d.set_spawn_point", icon='EMPTY_ARROWS')

        spawn = bpy.data.objects.get(SPAWN_NAME)
        if spawn:
            loc = spawn.location
            box2.label(text=f"At: {loc.x:.2f}, {loc.y:.2f}, {loc.z:.2f}")
        else:
            box2.label(text="No spawn point set", icon='ERROR')

        # --- Stats ---
        layout.operator("visite3d.show_stats", icon='INFO')


# -----------------------------------------------------------
# Register
# -----------------------------------------------------------

classes = [
    VISITE3D_OT_AddCollider,
    VISITE3D_OT_AddInvisibleWall,
    VISITE3D_OT_SetSpawnPoint,
    VISITE3D_OT_SelectColliders,
    VISITE3D_OT_ShowStats,
    VISITE3D_PT_Panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
