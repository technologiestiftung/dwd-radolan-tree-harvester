""" This script creates a grid of polygons for the area of interest. Current precipitation data can then be assigned to these cells using the harvester.py script.

Input:
    buffer.shp: Shapefile containing the outline of the area of interest as a polygon
    grid.asc: An example raster file conatining precipitation data for whole Germany
"""

import sys
import os
import logging
import psycopg2
import psycopg2.extras
import geopandas
import subprocess
import numpy
import linecache
from shapely.wkt import dumps
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig()
logging.root.setLevel(logging.INFO)

# name of folder that contains the data
temp = "temp"
# if os.path.isdir(temp) != True:
#   os.mkdir(temp)

# # grid file
# if (len(sys.argv) < 2):
#   logging.error("❌ Command line argument for grid file is missing")
# if os.path.isfile(sys.argv[1]) != True:
#   logging.error("❌ Grid file is not a valid file path")

# grid_file = sys.argv[1]

# check if all required environmental variables are accessible
for env_var in ["PG_DB", "PG_PORT", "PG_USER", "PG_PASS", "PG_SERVER"]:
    if env_var not in os.environ:
        logging.error(
            "❌Environmental Variable {} does not exist".format(env_var))

pg_server = os.getenv("PG_SERVER")
pg_port = os.getenv("PG_PORT")
pg_username = os.getenv("PG_USER")
pg_password = os.getenv("PG_PASS")
pg_database = os.getenv("PG_DB")

dsn = f"host='{pg_server}' port={pg_port} user='{pg_username}' password='{pg_password}' dbname='{pg_database}'"

logging.info("🆙 Starting grid")

try:
    conn = psycopg2.connect(dsn)
    logging.info("🗄 Database connection established")
except:
    logging.error("❌Could not establish database connection")
    conn = None

# we need to give each grid cell a unique value, otherwise gdal_polygonize will combine cells with equal values
asc_data = numpy.loadtxt(temp + "/grid.asc", skiprows=6)
col_value = 1
for r_idx, row in enumerate(asc_data):
    for c_idx, col in enumerate(row):
        asc_data[r_idx][c_idx] = col_value
        col_value += 1

header = linecache.getline(temp + "/grid.asc", 1) + \
    linecache.getline(temp + "/grid.asc", 2) + \
    linecache.getline(temp + "/grid.asc", 3) + \
    linecache.getline(temp + "/grid.asc", 4) + \
    linecache.getline(temp + "/grid.asc", 5) + \
    linecache.getline(temp + "/grid.asc", 6)

numpy.savetxt(temp + "/grid-transform.asc", asc_data,
              header=header.rstrip(), comments='', fmt='%i')

# use gdalwarp as commandline tool to crop the example weather dataset to the outline of our area of interest that is defined by the file buffer.shp
# with the arguments -s_srs and -t-srs we set the spatial reference systems for the source and the target files
# for our example weather data the srs is: "+proj=stere +lon_0=10.0 +lat_0=90.0 +lat_ts=60.0 +a=6370040 +b=6370040 +units=m"
cmdline = ['gdalwarp', temp + "/grid-transform.asc", temp + "/grid-buffer.asc", "-s_srs", "+proj=stere +lon_0=10.0 +lat_0=90.0 +lat_ts=60.0 +a=6370040 +b=6370040 +units=m",
           "-t_srs", "+proj=stere +lon_0=10.0 +lat_0=90.0 +lat_ts=60.0 +a=6370040 +b=6370040 +units=m", "-r", "near", "-of", "GTiff", "-cutline", "buffer.shp"]
subprocess.call(cmdline)

# use gdal_polygonize to transform the grid into a vector. a polygon is created for each pixel in our area of interest with a unique ID (MYFLD). these polygons form our grid and are saved in a shapefile. 
cmdline = [
    "gdal_polygonize.py",
    temp + "/grid-buffer.asc",
    "-f", "ESRI Shapefile",
    temp + "/grid.shp",
    "temp",
    "MYFLD",
    "-q"
]

subprocess.call(cmdline)

df = geopandas.read_file(temp + "/grid.shp")
df = df.to_crs("epsg:4326")

if df['geometry'].count() > 0:
    clean = df[(df['MYFLD'].notnull())]  # (df['MYFLD'] > 0) &
    if len(clean) > 0:
        values = []
        for index, row in clean.iterrows():
            values.append([dumps(row.geometry, rounding_precision=5)])

        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.radolan_geometry;")
            psycopg2.extras.execute_batch(
                cur,
                "INSERT INTO public.radolan_geometry (geometry) VALUES (ST_GeomFromText(%s, 4326));",
                values
            )
            conn.commit()

            cur.execute(
                "UPDATE public.radolan_geometry SET centroid = ST_Centroid(geometry);")
            conn.commit()

            cur.close()

conn.close()

logging.info("✅ Grid created")
