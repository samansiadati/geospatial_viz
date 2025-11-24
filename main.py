"""
Chicago Health Map Poster Generator
-----------------------------------

This script creates a 1-page PNG poster + an interactive HTML map
for ANY metric in your CSV (Birth Rate, Diabetes-related, etc.).

Requirements:
    pip install geopandas pandas matplotlib contextily folium pillow shapely

Place files here:
    data/chicago_community_areas.geojson
    data/chicago_health_metrics.csv   <-- Your CSV with columns:
        "Community Area Name", "Birth Rate", "Diabetes-related", ...
"""

from pathlib import Path
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import contextily as ctx
import folium
from folium.features import GeoJsonTooltip

# ----------------------
# Paths (corrected)
# ----------------------
BASE = Path.cwd()
DATA = BASE / "data"
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

GEO_PATH = DATA / "chicago-community-areas.geojson"
CSV_PATH = DATA / "public-health-statistics-selected-public-health-indicators-by-chicago-community-area-1.csv"

PNG_OUT = OUT / "chicago_health_poster.png"
HTML_OUT = OUT / "chicago_health_map.html"

# ----------------------
# LOAD DATA
# ----------------------
def load_geo():
    if not GEO_PATH.exists():
        raise FileNotFoundError(f"Missing {GEO_PATH.name} in {DATA}/")
    gdf = gpd.read_file(GEO_PATH)
    gdf.columns = [c.strip() for c in gdf.columns]
    return gdf

def load_csv():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing {CSV_PATH.name} in {DATA}/")
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    return df

# ----------------------
# MERGE
# ----------------------
def merge_data(gdf, df, metric):
    # Detect GEO join column
    gkey = None
    for c in gdf.columns:
        if "community" in c.lower():
            gkey = c
            break
    if gkey is None:
        raise RuntimeError("Could not find community field in geojson.")

    # CSV join column
    if "Community Area Name" not in df.columns:
        raise RuntimeError("CSV must contain 'Community Area Name' column.")

    gdf["__join__"] = gdf[gkey].astype(str).str.lower().str.strip()
    df["__join__"] = df["Community Area Name"].astype(str).str.lower().str.strip()

    merged = gdf.merge(df, on="__join__", how="left")

    if metric not in merged.columns:
        raise RuntimeError(f"Metric '{metric}' not found in CSV.")

    merged["metric_value"] = pd.to_numeric(merged[metric], errors="coerce")
    return merged

# ----------------------
# PLOT PNG POSTER
# ----------------------
def make_poster(merged, metric_name):
    merged = merged.to_crs(3857)

    vmin = merged["metric_value"].quantile(0.01)
    vmax = merged["metric_value"].quantile(0.99)

    fig, ax = plt.subplots(figsize=(11, 14), dpi=300)
    ax.set_axis_off()

    cmap = mpl.cm.inferno
    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

    merged.plot(
        column="metric_value",
        cmap=cmap,
        linewidth=0.5,
        edgecolor="white",
        ax=ax,
        norm=norm
    )

    try:
        ctx.add_basemap(
            ax,
            crs=merged.crs.to_string(),
            source=ctx.providers.CartoDB.Positron,
            alpha=0.4
        )
    except:
        print("[WARN] Basemap unavailable (offline).")

    # Title
    ax.set_title(
        f"{metric_name} Across Chicago Community Areas",
        fontsize=22, weight="bold", pad=25
    )

    # Colorbar
    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm._A = []
    cax = fig.add_axes([0.20, 0.05, 0.60, 0.025])
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.set_label(metric_name, fontsize=10)

    # Caption
    caption = (
        f"This map shows spatial patterns of {metric_name.lower()} in Chicago. "
        "Darker colors represent higher values. "
        "These patterns highlight how health outcomes vary across neighborhoods, "
        "often reflecting structural, environmental, and socioeconomic factors."
    )
    fig.text(0.5, 0.015, caption, ha="center", fontsize=10)

    fig.savefig(PNG_OUT, bbox_inches="tight", dpi=300)
    plt.close()
    print(f"[INFO] Poster saved → {PNG_OUT}")

# ----------------------
# INTERACTIVE HTML MAP
# ----------------------
def make_interactive(merged, metric_name):
    merged = merged.to_crs(4326)
    center = [
        merged.geometry.centroid.y.mean(),
        merged.geometry.centroid.x.mean()
    ]

    m = folium.Map(location=center, zoom_start=10, tiles="CartoDB Positron")

    folium.Choropleth(
        geo_data=merged.__geo_interface__,
        name="choropleth",
        data=merged,
        columns=["__join__", "metric_value"],
        key_on="feature.properties.__join__",
        fill_color="YlOrRd",
        fill_opacity=0.85,
        line_opacity=0.3,
        legend_name=metric_name
    ).add_to(m)

    tooltip_cols = ["Community Area Name", "metric_value"] if "Community Area Name" in merged.columns else ["metric_value"]

    folium.GeoJson(
        merged,
        tooltip=GeoJsonTooltip(
            fields=tooltip_cols,
            aliases=["Community Area", metric_name],
            localize=True
        )
    ).add_to(m)

    m.save(HTML_OUT)
    print(f"[INFO] Interactive map saved → {HTML_OUT}")

# ----------------------
# MAIN
# ----------------------
def main():
    print("\n=== Chicago Health Poster Generator ===")

    gdf = load_geo()
    df = load_csv()

    print("\nYour CSV columns:")
    print(df.columns.tolist())

    # Ask user what metric to map
    print("\nEnter the EXACT column name you want to map:")
    metric = input("Metric: ").strip()

    merged = merge_data(gdf, df, metric)

    make_poster(merged, metric)
    make_interactive(merged, metric)

    print("\nDONE! Your poster and HTML map are in /output/\n")


if __name__ == "__main__":
    main()
