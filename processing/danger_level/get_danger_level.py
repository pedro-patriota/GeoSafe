import time
from typing import Union

from geopandas import read_file, GeoDataFrame
from pandas import DataFrame, read_csv, concat
from shapely.geometry import Point

from base.pandas_constants import (
    PathConstants,
    DataFrameConstants, ValuesConstants, DangerLevelConstants
)
from base.pandas_helper import PandasHelper


class GetDangerLevel:
    """
    Gets the danger level based on the location
    """

    @staticmethod
    def check_point_in_geojson(gdf: GeoDataFrame, latitude: float, longitude: float) -> Union[str, None]:
        """Check if a point defined by latitude and longitude is within a geojson and determine its danger level."""
        point = Point(longitude, latitude)
        for index, row in gdf.iterrows():
            geometry = row[DangerLevelConstants.GEOMETRY]
            if geometry.contains(point):
                danger_level_class = (
                    row[DangerLevelConstants.CLASSE]
                    if row[DangerLevelConstants.CLASSE] != DangerLevelConstants.WRONG_MEDIA
                    else DangerLevelConstants.CORRECT_MEDIA
                )
                print(f'Found danger level of point {point}')
                return danger_level_class
        print(f'Did not find danger level of point {point}')
        return None

    @staticmethod
    def get_danger_level(
            df_ground_type: DataFrame,
            df_bad_danger_level: DataFrame,
            df_found_danger_level: DataFrame,
            path_found: str = PathConstants.LANDSLIDE_FOUND_DANGER_LEVEL_PATH,
            path_bad: str = PathConstants.LANDSLIDE_BAD_DANGER_LEVEL_PATH,
            batch_size: int = 10
    ) -> None:
        """Process batches of data to determine danger levels and update DataFrames accordingly."""
        df_outer_bad = PandasHelper.get_outer_merge(df_ground_type, df_bad_danger_level)
        df_outer_found = PandasHelper.get_outer_merge(df_outer_bad, df_found_danger_level)

        print(f'There are {len(df_outer_found)} occurrences not processed')
        print(f'Reading batch of size {batch_size}')

        df_outer_found = df_outer_found.iloc[:batch_size]
        df_outer_found[DataFrameConstants.DANGER_LEVEL] = ValuesConstants.UNKNOWN_VALUE

        gdf = read_file(PathConstants.MOVIMENTO_MASSA_PATH, encoding='utf-8')

        for index, occurrence in df_outer_found.iterrows():
            latitude = occurrence[DataFrameConstants.LATITUDE]
            longitude = occurrence[DataFrameConstants.LONGITUDE]

            danger_level = GetDangerLevel.check_point_in_geojson(gdf, latitude, longitude)

            df_outer_found.loc[index, DataFrameConstants.DANGER_LEVEL] = danger_level

        df_bad_rows = df_outer_found[df_outer_found[DataFrameConstants.DANGER_LEVEL].isna()]
        df_good_rows = df_outer_found[df_outer_found[DataFrameConstants.DANGER_LEVEL].notna()]

        df_bad_danger_level = concat([df_bad_danger_level, df_bad_rows], ignore_index=True)
        df_found_danger_level = concat([df_found_danger_level, df_good_rows], ignore_index=True)

        df_bad_danger_level.to_csv(path_bad, index=False, header=True)
        df_found_danger_level.to_csv(path_found, index=False, header=True)


if __name__ == '__main__':
    while True:
        df_ground_type = read_csv(PathConstants.NO_LANDSLIDE_FOUND_GROUND_AMPLITUDE_PATH)

        path_found = PathConstants.NO_LANDSLIDE_FOUND_DANGER_LEVEL_PATH
        path_bad = PathConstants.NO_LANDSLIDE_BAD_DANGER_LEVEL_PATH

        df_found_danger_level = PandasHelper.safe_read_csv(path_found, df_ground_type.columns.to_list())
        df_bad_danger_level = PandasHelper.safe_read_csv(path_bad, df_ground_type.columns.to_list())

        if len(df_ground_type) == len(df_found_danger_level) + len(df_bad_danger_level):
            print("There is no row to process")
            break

        try:
            GetDangerLevel.get_danger_level(
                df_ground_type=df_ground_type,
                df_bad_danger_level=df_bad_danger_level,
                df_found_danger_level=df_found_danger_level,
                path_found=path_found,
                path_bad=path_bad,
                batch_size=1000
            )
            print("Finished reading batch")
        except Exception as error:
            print(error, error.__str__())
            print("Applying 10 minutes delay and trying once more...")
            time.sleep(60 * 10)
