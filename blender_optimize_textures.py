# ============================================================
# 3D Visite — Texture Optimizer Script
# ============================================================
# Usage:
#   1. Open your scene in Blender
#   2. Open this script in the Scripting tab
#   3. Use the panel in the sidebar (N panel > 3D Visite)
#
# Features:
#   - Resize all textures to a max resolution
#   - Resize only selected objects' textures
#   - Convert to JPEG (smaller) or keep PNG (alpha)
#   - Preview total texture memory before/after
# ============================================================

import bpy
import os

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

RESIZE_PRESETS = [
    ("256", "256px", ""),
    ("512", "512px", ""),
    ("1024", "1K", ""),
    ("2048", "2K", ""),
    ("4096", "4K", ""),
]


def get_images_from_objects(objects):
    """Collect all unique images used by a set of objects."""
    images = set()
    for obj in objects:
        if obj.type != 'MESH' or not obj.data.materials:
            continue
        for mat in obj.data.materials:
            if mat is None or not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    images.add(node.image)
    return images


def get_all_images():
    """Collect all images used by any material in the scene."""
    images = set()
    for mat in bpy.data.materials:
        if mat is None or not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                images.add(node.image)
    return images


def calc_memory(images):
    """Estimate VRAM usage in MB (width * height * 4 bytes)."""
    total = 0
    for img in images:
        total += img.size[0] * img.size[1] * 4
    return total / (1024 * 1024)


def resize_image(image, max_size):
    """Resize an image if either dimension exceeds max_size."""
    w, h = image.size
    if w <= max_size and h <= max_size:
        return False

    if w >= h:
        new_w = max_size
        new_h = max(1, int(h * (max_size / w)))
    else:
        new_h = max_size
        new_w = max(1, int(w * (max_size / h)))

    image.scale(new_w, new_h)
    return True


# -----------------------------------------------------------
# Operators
# -----------------------------------------------------------

class VISITE3D_OT_ResizeAllTextures(bpy.types.Operator):
    bl_idname = "visite3d.resize_all_textures"
    bl_label = "Resize All Textures"
    bl_description = "Resize all textures in the scene to the chosen max resolution"
    bl_options = {'REGISTER', 'UNDO'}

    max_size: bpy.props.EnumProperty(
        name="Max Size",
        items=RESIZE_PRESETS,
        default="1024",
    )

    def execute(self, context):
        images = get_all_images()
        mem_before = calc_memory(images)
        count = 0
        for img in images:
            if resize_image(img, int(self.max_size)):
                count += 1
        mem_after = calc_memory(images)

        self.report({'INFO'},
            f"{count}/{len(images)} texture(s) resized to max {self.max_size}px — "
            f"{mem_before:.1f} MB → {mem_after:.1f} MB")
        return {'FINISHED'}


class VISITE3D_OT_ResizeSelectedTextures(bpy.types.Operator):
    bl_idname = "visite3d.resize_selected_textures"
    bl_label = "Resize Selected Textures"
    bl_description = "Resize textures of selected objects only"
    bl_options = {'REGISTER', 'UNDO'}

    max_size: bpy.props.EnumProperty(
        name="Max Size",
        items=RESIZE_PRESETS,
        default="1024",
    )

    def execute(self, context):
        images = get_images_from_objects(context.selected_objects)
        if not images:
            self.report({'WARNING'}, "No textures found on selected objects")
            return {'CANCELLED'}

        mem_before = calc_memory(images)
        count = 0
        for img in images:
            if resize_image(img, int(self.max_size)):
                count += 1
        mem_after = calc_memory(images)

        self.report({'INFO'},
            f"{count}/{len(images)} texture(s) resized — "
            f"{mem_before:.1f} MB → {mem_after:.1f} MB")
        return {'FINISHED'}


class VISITE3D_OT_TextureStats(bpy.types.Operator):
    bl_idname = "visite3d.texture_stats"
    bl_label = "Texture Stats"
    bl_description = "Show texture count, sizes, and estimated memory"

    def execute(self, context):
        images = get_all_images()
        if not images:
            self.report({'INFO'}, "No textures found")
            return {'FINISHED'}

        mem = calc_memory(images)
        sizes = {}
        for img in images:
            key = f"{img.size[0]}x{img.size[1]}"
            sizes[key] = sizes.get(key, 0) + 1

        breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(sizes.items(), key=lambda x: -x[1]))
        self.report({'INFO'}, f"{len(images)} texture(s), ~{mem:.1f} MB — {breakdown}")
        return {'FINISHED'}


class VISITE3D_OT_PackAndConvert(bpy.types.Operator):
    bl_idname = "visite3d.pack_and_convert"
    bl_label = "Convert to JPEG"
    bl_description = "Convert non-alpha textures to JPEG format (smaller file size for GLB export)"
    bl_options = {'REGISTER', 'UNDO'}

    quality: bpy.props.IntProperty(
        name="Quality",
        default=85,
        min=10,
        max=100,
    )

    def execute(self, context):
        images = get_all_images()
        count = 0
        for img in images:
            # Skip images with alpha channel actually used
            if img.channels == 4 and img.alpha_mode != 'NONE':
                # Check if any pixel actually has non-opaque alpha
                has_alpha = False
                if img.size[0] * img.size[1] <= 4096 * 4096:
                    pixels = list(img.pixels)
                    # Sample alpha channel (every 4th value starting at index 3)
                    for i in range(3, len(pixels), 4 * 64):  # sample every 64th pixel
                        if pixels[i] < 0.99:
                            has_alpha = True
                            break
                if has_alpha:
                    continue

            img.file_format = 'JPEG'
            img.pack()
            count += 1

        self.report({'INFO'}, f"{count}/{len(images)} texture(s) converted to JPEG")
        return {'FINISHED'}


class VISITE3D_OT_ListLargeTextures(bpy.types.Operator):
    bl_idname = "visite3d.list_large_textures"
    bl_label = "List Large Textures"
    bl_description = "Print textures larger than 2K to the console"

    def execute(self, context):
        images = get_all_images()
        large = [(img.name, img.size[0], img.size[1]) for img in images
                 if img.size[0] > 2048 or img.size[1] > 2048]

        if not large:
            self.report({'INFO'}, "No textures above 2K")
        else:
            for name, w, h in sorted(large, key=lambda x: -(x[1]*x[2])):
                print(f"  {name}: {w}x{h}")
            self.report({'WARNING'}, f"{len(large)} texture(s) above 2K — see console")
        return {'FINISHED'}


# -----------------------------------------------------------
# Panel
# -----------------------------------------------------------

class VISITE3D_PT_TexturePanel(bpy.types.Panel):
    bl_label = "Texture Optimizer"
    bl_idname = "VISITE3D_PT_texture_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "3D Visite"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # --- Stats ---
        images = get_all_images()
        mem = calc_memory(images)

        box = layout.box()
        box.label(text="Stats", icon='IMAGE_DATA')
        box.label(text=f"{len(images)} texture(s) — ~{mem:.1f} MB VRAM")
        box.operator("visite3d.texture_stats", icon='INFO')
        box.operator("visite3d.list_large_textures", icon='ZOOM_ALL')

        # --- Resize All ---
        box2 = layout.box()
        box2.label(text="Resize", icon='FULLSCREEN_EXIT')

        row = box2.row(align=True)
        row.label(text="All textures:")
        for preset in RESIZE_PRESETS:
            op = row.operator("visite3d.resize_all_textures", text=preset[1])
            op.max_size = preset[0]

        row2 = box2.row(align=True)
        row2.label(text="Selected only:")
        for preset in RESIZE_PRESETS:
            op = row2.operator("visite3d.resize_selected_textures", text=preset[1])
            op.max_size = preset[0]

        # --- Convert ---
        box3 = layout.box()
        box3.label(text="Format", icon='FILE_IMAGE')
        box3.operator("visite3d.pack_and_convert", icon='IMAGE_DATA')


# -----------------------------------------------------------
# Register
# -----------------------------------------------------------

tex_classes = [
    VISITE3D_OT_ResizeAllTextures,
    VISITE3D_OT_ResizeSelectedTextures,
    VISITE3D_OT_TextureStats,
    VISITE3D_OT_PackAndConvert,
    VISITE3D_OT_ListLargeTextures,
    VISITE3D_PT_TexturePanel,
]

def register():
    for cls in tex_classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(tex_classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
