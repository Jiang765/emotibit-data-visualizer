# EmotiBit Data Visualization

A Python script to visualize EmotiBit sensor data with music playback annotations.

## Features

- Plots multiple EmotiBit sensor signals (accelerometer, gyroscope, PPG, EDA, temperature, heart rate)
- Annotates music playback periods on each plot
- Automatically adjusts plot height to accommodate annotations
- Saves high-resolution plots as PNG files

## Requirements

- Python 3.x
- pandas
- matplotlib
- openpyxl (for Excel support)

## Usage

1. **Configure paths** in the script:

   - `DATA_FOLDER_PATH`: Folder containing EmotiBit CSV files
   - `MUSIC_SCHEDULE_PATH`: Excel file with music schedule
   - `OUTPUT_FOLDER`: Where to save plot images

2. **Data format**:

   - EmotiBit files: `*_XX.csv` where XX is the signal type (e.g., `data_AX.csv`)
   - Music schedule: Excel with columns [time, song_name]

3. **Run the notebook**:

   - Open Jupyter Notebook or JupyterLab
   - Navigate to the notebook file
   - Run all cells (Cell → Run All)

## Output

- Individual plots for each signal type
- Gray shaded regions indicate music playback periods
- Plots saved to `OUTPUT_FOLDER` as PNG files

## Customization

Edit the `CHANNELS` dictionary to add/remove signals or modify the `FIGURE_SIZE` and annotation colors in the configuration section.