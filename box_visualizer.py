import matplotlib.pyplot as plt
from matplotlib.patches import Polygon


# ==========================================
# 1. CORE ISOMETRIC PROJECTION
# ==========================================
def project_3d_to_2d(X, Y, Z, x0=0, y0=0):
    """
    3D -> 2D isometric projection

    X = right
    Y = depth
    Z = height
    """

    screen_x = x0 + (0.866 * X) - (0.866 * Y)
    screen_y = y0 - (0.5 * X) - (0.5 * Y) + Z

    return screen_x, screen_y


# ==========================================
# 2. DRAW BOX
# ==========================================
def draw_procedural_box(L, W, H, unit="mm"):

    fig, ax = plt.subplots(figsize=(8, 8))

    x0, y0 = 0, 0

    # ==========================================
    # 3. BOX VERTICES
    # ==========================================
    vertices3d = [
        (0, 0, 0),      # 0
        (L, 0, 0),      # 1
        (L, W, 0),      # 2
        (0, W, 0),      # 3
        (0, 0, H),      # 4
        (L, 0, H),      # 5
        (L, W, H),      # 6
        (0, W, H)       # 7
    ]

    # Project all vertices to 2D
    points2d = [
        project_3d_to_2d(x, y, z, x0, y0)
        for x, y, z in vertices3d
    ]
    
    # DEBUG: show vertex numbers
    """for i, p in enumerate(points2d):
        ax.text(
            p[0],
            p[1],
            str(i),
            color='red',
            fontsize=12,
            fontweight='bold'
        )
    """
    
    # ==========================================
    # 4. CORRECT VISIBLE FACES
    # ==========================================
    faces = [

        # RIGHT / Y FACE
        {
            "indices": [6, 5, 1, 2],
            "color": "#b58150"
        },
        # TOP FACE
        {
            "indices": [4, 5, 6, 7],
            "color": "#eac5a3"
        },
        # LEFT / X FACE
        {
            "indices": [7, 6, 2, 3],
            "color": "#d3a270"
        }
    ]

    # ==========================================
    # 5. DEPTH SORT
    # ==========================================
    for face in faces:

        depth = 0

        for idx in face["indices"]:
            x, y, z = vertices3d[idx]
            depth += x + y + z

        face["depth"] = depth / 4

    # ==========================================
    # 6. DRAW FACES
    # ==========================================
    for face in faces:

        polygon_points = [
            points2d[i]
            for i in face["indices"]
        ]

        poly = Polygon(
            polygon_points,
            closed=True,
            facecolor=face["color"],
            linewidth=0,
        )

        ax.add_patch(poly)

    # ==========================================
    # 7. AXIS INDICATOR
    # ==========================================
    axis_size = max(L, W, H) * 0.25

    ax_origin_x = -max(L, W) * 0.8
    ax_origin_y = -max(L, W) * 0.8

    origin = project_3d_to_2d(
        0, 0, 0,
        ax_origin_x,
        ax_origin_y
    )

    axis_x = project_3d_to_2d(
        axis_size, 0, 0,
        ax_origin_x,
        ax_origin_y
    )

    axis_y = project_3d_to_2d(
        0, -axis_size, 0,
        ax_origin_x,
        ax_origin_y
    )

    axis_z = project_3d_to_2d(
        0, 0, axis_size,
        ax_origin_x,
        ax_origin_y
    )

    # arrows
    ax.annotate(
        '',
        xy=axis_x,
        xytext=origin,
        arrowprops=dict(
            arrowstyle='->',
            color='red',
            lw=2
        )
    )

    ax.annotate(
        '',
        xy=axis_y,
        xytext=origin,
        arrowprops=dict(
            arrowstyle='->',
            color='green',
            lw=2
        )
    )

    ax.annotate(
        '',
        xy=axis_z,
        xytext=origin,
        arrowprops=dict(
            arrowstyle='->',
            color='dodgerblue',
            lw=2
        )
    )

    ax.text(axis_x[0], axis_x[1], "X", color='red')
    ax.text(axis_y[0], axis_y[1], "Y", color='green')
    ax.text(axis_z[0], axis_z[1], "Z", color='dodgerblue')

    # ==========================================
    # 8. DIMENSION LABELS
    # ==========================================
    pad = max(L, W, H) * 0.06

    # Length (X edge)
    l_mid = project_3d_to_2d(L / 2, 0, 0)

    ax.text(
        l_mid[0],
        l_mid[1] - pad,
        f"L = {L} {unit}",
        color='white',
        fontsize=12
    )

    # Width (Y edge)
    w_mid = project_3d_to_2d(0, W / 2, 0)

    ax.text(
        w_mid[0] - pad,
        w_mid[1],
        f"W = {W} {unit}",
        color='white',
        fontsize=12
    )

    # Height (Z edge)
    h_mid = project_3d_to_2d(0, 0, H / 2)

    ax.text(
        h_mid[0] - pad,
        h_mid[1],
        f"H = {H} {unit}",
        color='white',
        fontsize=12
    )

    # ==========================================
    # 9. STYLE
    # ==========================================
    fig.patch.set_facecolor('#1e1e1e')
    ax.set_facecolor('#1e1e1e')

    ax.set_aspect('equal')
    ax.axis('off')

    padding = max(L, W, H)

    ax.set_xlim(-padding * 1.5, padding * 1.5)
    ax.set_ylim(-padding * 1.2, padding * 1.5)

    plt.show()


# ==========================================
# RUN
# ==========================================
draw_procedural_box(
    L=6.0,
    W=5.0,
    H=7.0,
    unit="cm"
)