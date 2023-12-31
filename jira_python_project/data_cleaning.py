# data_cleaning.py

"""
This module provides functionality for cleaning and transforming the detailed data
retrieved from JIRA into a more structured and useful format.
"""

import pandas as pd
import re
import os

from logger_config import logger
from config import Config

def clean_datetime(value):
    """
    Cleans datetime strings by removing fractional seconds and timezone information.

    Parameters:
    value (str): The datetime string to be cleaned.

    Returns:
    str: The cleaned datetime string.
    """
    return re.sub(r'\.\d+\+\d+:\d+', '', value) if isinstance(value, str) else value


def transform_and_clean_data(detailed_df: pd.DataFrame, summary_df: pd.DataFrame, stats_df: pd.DataFrame, version_name: str) -> pd.DataFrame:
    """
    Transforms and cleans the detailed DataFrame. It also writes the processed data into CSV files.

    Parameters:
    detailed_df (pd.DataFrame): The detailed DataFrame.
    summary_df (pd.DataFrame): The summary DataFrame.
    stats_df (pd.DataFrame): The statistics DataFrame.
    version_name (str): The version name, used for naming output files.

    Returns:
    pd.DataFrame: The transformed and cleaned DataFrame.
    """
    
    if detailed_df.empty or not all(col in detailed_df.columns for col in ['Key', 'Changelog_and_Time']):
        logger.warning(f"No data to transform and clean for {version_name}")
        return pd.DataFrame()
    
    data_list = detailed_df[['Key', 'Changelog_and_Time']]
    dfs = []

    for index, row in data_list.iterrows():
        key = row['Key']
        changelog_and_time = row['Changelog_and_Time']
        df = pd.DataFrame(changelog_and_time, columns=['Date', 'Status'])
        df['Date'] = pd.to_datetime(df['Date'], utc=True)
        df['Key'] = key
        dfs.append(df)

    df_result = pd.concat(dfs)
    df_result['Status_ID'] = df_result.groupby(['Key', 'Status']).cumcount() + 1
    df_result_pivoted = df_result.pivot(index='Key', columns=['Status', 'Status_ID'], values='Date')
    df_result_pivoted.columns = [f"{col[0]} {col[1]}" for col in df_result_pivoted.columns]
    df_result_pivoted.reset_index(inplace=True)

    replacement_dict = df_result_pivoted.set_index('Key').to_dict(orient='index')
    detailed_df['Changelog_and_Time'] = detailed_df['Key'].map(replacement_dict)
    detailed_df = detailed_df.merge(df_result_pivoted, on='Key', how='left').drop('Changelog_and_Time', axis=1)
    detailed_df['Create_Date'] = pd.to_datetime(detailed_df['Create_Date'], utc=True)

    datetime_columns = detailed_df.columns[detailed_df.columns.get_loc('Create_Date'):]
    detailed_df[datetime_columns] = detailed_df[datetime_columns].map(clean_datetime)
    
    # Create a version-specific directory
    version_directory = os.path.join(Config.DATA_DIRECTORY, version_name)
    os.makedirs(version_directory, exist_ok=True)
    
    # Saving to CSV files (consider moving this to a separate function)
    try:
        # Save CSVs in the version-specific directory
        detailed_filename = os.path.join(version_directory, f"{version_name}-detailed.csv")
        summary_filename = os.path.join(version_directory, f"{version_name}-summary.csv")
        stats_filename = os.path.join(version_directory, f"{version_name}-stats.csv")

        detailed_df.to_csv(detailed_filename, encoding='utf-8')
        summary_df.to_csv(summary_filename, encoding='utf-8')
        stats_df.to_csv(stats_filename, encoding='utf-8')
        
    except Exception as e:
        logger.error(f"Error writing to CSV files: {e}")
        raise

    return detailed_df