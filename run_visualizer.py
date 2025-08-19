import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime
import glob
import textwrap
import subprocess
import sys

# --- Global Configuration ---

# 1. Root Dataset Folder
#    This script will process all subfolders under this directory.
ROOT_DATASET_FOLDER = '../PwD dataset-2'

# 2. Channels and Descriptions
CHANNELS = {
    'AX': 'Accelerometer X', 'AY': 'Accelerometer Y', 'AZ': 'Accelerometer Z',
    'GX': 'Gyroscope X', 'GY': 'Gyroscope Y', 'GZ': 'Gyroscope Z',
    'EA': 'Electrodermal Activity', 'EL': 'Electrodermal Level',
    'SF': 'SCR Frequency', 'SA': 'SCR Amplitude', 'SR': 'SCR Rise Time',
    'T1': 'Temperature', 'TH': 'Thermopile Temperature',
    'PI': 'PPG Infrared', 'PR': 'PPG Red', 'PG': 'PPG Green',
    'BI': 'Beat Interval', 'HR': 'Heart Rate',
}
SIGNALS_TO_PLOT = list(CHANNELS.keys())

# 3. Plot Styling
FIGURE_SIZE = (22, 7)
ANNOTATION_BACKGROUND_COLOR = 'grey'
ANNOTATION_ALPHA = 0.2

# --- Core Functions ---

def install_packages():
    """Checks and installs required packages."""
    required_packages = ['pandas', 'matplotlib', 'openpyxl']
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    print("All required packages are installed.")

def load_emotibit_data(folder_path, signals_to_plot):
    """Loads and processes EmotiBit CSV files from a specified folder."""
    print(f"--- Starting EmotiBit Data Loading from '{folder_path}' ---")
    dataframes = {}
    experiment_date_str = None
    
    try:
        all_files = glob.glob(os.path.join(folder_path, '*.csv'))
        if not all_files:
            print(f"Error: No CSV files found in '{folder_path}'. Please check the path.")
            return {}, None
    except Exception as e:
        print(f"Error: Could not access folder '{folder_path}'. {e}")
        return {}, None

    for file_path in all_files:
        basename = os.path.basename(file_path)
        try:
            date_part = basename.split('_')[0]
            datetime.datetime.strptime(date_part, '%Y-%m-%d')
            experiment_date_str = date_part.replace('-', '')
            print(f"Successfully extracted experiment date: {experiment_date_str} from filename '{basename}'")
            break
        except (ValueError, IndexError):
            continue
    
    if not experiment_date_str:
        print("Error: Could not parse experiment date from any filename.")
        return {}, None

    for signal_type in signals_to_plot:
        file_pattern = os.path.join(folder_path, f"*_{signal_type}.csv")
        found_files = glob.glob(file_pattern)
        if not found_files:
            continue
        file_path = found_files[0]
        try:
            df = pd.read_csv(file_path)
            if 'LocalTimestamp' not in df.columns or df.shape[1] < 2:
                continue
            signal_column_name = df.columns[-1]
            df['est_time'] = pd.to_datetime(df['LocalTimestamp'], unit='s').dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
            df.rename(columns={signal_column_name: 'value'}, inplace=True)
            dataframes[signal_type] = df[['est_time', 'value']]
        except Exception as e:
            print(f"  - Error processing file '{os.path.basename(file_path)}': {e}")
            
    print(f"--- EmotiBit Data Loading Complete. Loaded {len(dataframes)} signals. ---\n")
    return dataframes, experiment_date_str

def load_music_schedule(file_path, experiment_date_str, data_folder_path):
    """
    Loads the schedule from a CSV file, includes the new 'Score' column,
    and prepares annotations for each specific time point.
    """
    print(f"--- Starting Schedule Loading from '{file_path}' ---")
    if not os.path.exists(file_path):
        print(f"Info: Schedule file not found. Plots will not have annotations.")
        return None
    try:
        # Read from CSV, now including the 'score' column
        df_schedule = pd.read_csv(
            file_path, 
            header=0, 
            usecols=[0, 1, 2, 3], 
            names=['time_str', 'song_artist', 'score', 'observation']
        )
        df_schedule.dropna(how='all', inplace=True)
        if df_schedule.empty:
            return None
    except Exception as e:
        print(f"Error: Failed to read schedule CSV file: {e}")
        return None

    is_afternoon = 'afternoon' in data_folder_path.lower()
    time_period = "PM" if is_afternoon else "AM"
    print(f"  - Detected '{time_period}' session. Adjusting times accordingly.")

    annotations = []
    first_song_start_time = None
    final_end_time = None

    def parse_time(time_str, date_str, is_pm):
         # Clean the string by removing AM/PM suffixes, case-insensitively
        cleaned_time_str = time_str.lower().replace('am', '').replace('pm', '').strip()
        try:
            # First, try to parse with seconds (e.g., '10:15:30')
            time_obj = datetime.datetime.strptime(cleaned_time_str, '%H:%M:%S').time()
        except ValueError:
            # If that fails, try to parse without seconds (e.g., '11:15')
            time_obj = datetime.datetime.strptime(cleaned_time_str, '%H:%M').time()
        
        hour = time_obj.hour
        if is_pm and 1 <= hour <= 11:
            hour += 12
        full_datetime_str = f"{date_str} {hour:02d}:{time_obj.minute:02d}:{time_obj.second:02d}"
        dt_naive = datetime.datetime.strptime(full_datetime_str, '%Y%m%d %H:%M:%S')
        return pd.Timestamp(dt_naive, tz='US/Eastern')

    all_events = []
    for index, row in df_schedule.iterrows():
        try:
            current_row_time = parse_time(str(row['time_str']).strip(), experiment_date_str, is_afternoon)
            # Handle blank cells for song_artist
            song_artist = str(row['song_artist']).strip() if pd.notna(row['song_artist']) else ""
            score = str(row['score']).strip() if pd.notna(row['score']) else ""
            observation = str(row['observation']).strip() if pd.notna(row['observation']) else ""
            all_events.append({'time': current_row_time, 'song': song_artist, 'score': score, 'obs': observation})
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not parse time '{row['time_str']}' on Excel row {index+2}. Skipping. Error: {e}")
            continue
    
    if not all_events:
        return None

    # Determine the start and end of the music session
    for event in all_events:
        # First non-empty song marks the start
        if event['song'] and first_song_start_time is None:
            first_song_start_time = event['time']
            print(f"  - Music session starts at: {first_song_start_time.strftime('%H:%M:%S')}")
        
        # "Music end" in the observation column marks the end
        if 'music end' in event['obs'].lower():
            final_end_time = event['time']
            print(f"  - Music session ends at: {final_end_time.strftime('%H:%M:%S')}")
            break # Stop searching once found

    if final_end_time is None:
        final_end_time = all_events[-1]['time']
        print(f"  - Music session ends at: {final_end_time.strftime('%H:%M:%S')}")

    for event in all_events:
        # Build the annotation text, now including the score
        text_parts = []
        if event['song']:
            text_parts.append(event['song'])
        if event['score']:
            text_parts.append(f"(Score: {event['score']})")
        if event['obs']:
            text_parts.append(event['obs'])
        combined_text = "\n".join(text_parts)
        
        annotations.append({'time': event['time'], 'text': combined_text})
        print(f"  - Created Annotation at: {event['time'].strftime('%H:%M:%S')}")
        print(f"    - Song: {event['song'] or 'N/A'}")
        print(f"    - Score: {event['score'] or 'N/A'}")
        print(f"    - Obs.: {event['obs'] or 'N/A'}")

    return {'annotations': annotations, 'music_start': first_song_start_time, 'music_end': final_end_time}

def plot_and_save_signal(signal_name, df, schedule_data, channel_map, output_folder):
    """Plots a single signal with annotations for each time point and saves the figure."""
    if df.empty or df['est_time'].isnull().all():
        return

    annotations = schedule_data.get('annotations', []) if schedule_data else []
    music_start = schedule_data.get('music_start', None) if schedule_data else None
    music_end = schedule_data.get('music_end', None) if schedule_data else None

    total_annotation_lines = sum(item['text'].count('\n') + 1 for item in annotations)
    base_height = 6
    extra_height_per_line = 0.3
    dynamic_height = base_height + (total_annotation_lines * extra_height_per_line)
    
    fig, ax = plt.subplots(figsize=(FIGURE_SIZE[0], dynamic_height))
    ax.plot(df['est_time'], df['value'], label=signal_name, color='royalblue', linewidth=1.5)
    min_time_data, max_time_data = df['est_time'].min(), df['est_time'].max()
    ax.set_xlim(min_time_data, max_time_data)
    
    # Draw a single gray background for the entire music session
    if music_start and music_end:
        ax.axvspan(music_start, music_end, color=ANNOTATION_BACKGROUND_COLOR, alpha=ANNOTATION_ALPHA, zorder=0)
    
    stagger_level = 0
    y_level_start, y_level_step = -0.15, -0.08
    for annotation in annotations:
        time_point = annotation['time']
        annotation_text = annotation['text']
        
        if not (min_time_data <= time_point <= max_time_data):
            continue
        
        y_level_for_text = y_level_start + (stagger_level * y_level_step)
        
        ax.annotate(
            annotation_text, xy=(time_point, 0), xycoords=('data', 'axes fraction'),
            xytext=(time_point, y_level_for_text), textcoords=('data', 'axes fraction'),
            ha='center', va='top', fontsize=10,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="gray", lw=0.5, zorder=2),
            arrowprops=dict(arrowstyle="-", linestyle=(0, (5, 10)), color='gray', shrinkA=5, zorder=1)
        )
        stagger_level += 1

    full_signal_name = channel_map.get(signal_name, signal_name)
    ax.set_title(f'EmotiBit Signal: {signal_name} ({full_signal_name})', fontsize=18, pad=20)
    ax.set_xlabel('Time (EST)', fontsize=12)
    ax.set_ylabel('Value', fontsize=12)
    ax.grid(True, axis='y', which='major', linestyle=':', color='gray', linewidth=0.8, alpha=0.7)
    ax.legend(loc='upper left')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S', tz='US/Eastern'))
    fig.autofmt_xdate()
    
    output_filename = f"{signal_name}_plot.png"
    full_output_path = os.path.join(output_folder, output_filename)
    fig.savefig(full_output_path, dpi=150, bbox_inches='tight', pad_inches=0.1)
    print(f"  - Plot saved to: {full_output_path}")
    plt.close(fig)

# --- Outer Wrapper and Main Loop ---

def process_folder(folder_path):
    """Main processing logic for a single data folder."""
    print(f"\n{'='*80}\nProcessing folder: {folder_path}\n{'='*80}")
    
    emotibit_data_path = folder_path
    music_schedule_path = glob.glob(os.path.join(folder_path, '* Combined Observations.csv'))[0]
    output_folder_path = os.path.join(folder_path, 'plots')
    
    if not os.path.isdir(emotibit_data_path):
        print(f"Error: 'emotibit_data' subfolder not found in {folder_path}. Skipping.")
        return
    if not os.path.exists(music_schedule_path):
        print(f"Error: 'music.xlsx' not found in {folder_path}. Skipping.")
        return
        
    os.makedirs(output_folder_path, exist_ok=True)
    
    emotibit_data, date_str = load_emotibit_data(emotibit_data_path, SIGNALS_TO_PLOT)
    if not date_str:
        print("Could not determine date. Aborting processing for this folder.")
        return
        
    schedule_data = load_music_schedule(music_schedule_path, date_str, folder_path)
    
    if not emotibit_data:
        print("No EmotiBit data was loaded. No plots will be generated.")
        return

    print(f"\n--- Generating and Saving {len(emotibit_data)} Plots to '{output_folder_path}' ---\n")
    for signal, df in emotibit_data.items():
        plot_and_save_signal(signal, df, schedule_data, CHANNELS, output_folder_path)
    print("\n--- Finished processing folder ---")


if __name__ == "__main__":
    install_packages()
    
    if not os.path.isdir(ROOT_DATASET_FOLDER):
        print(f"Error: Root dataset folder '{ROOT_DATASET_FOLDER}' not found.")
        print("Please make sure this script is in the same directory as the 'PwD dataset' folder.")
    else:
        subfolders = [f.path for f in os.scandir(ROOT_DATASET_FOLDER) if f.is_dir()]
        
        if not subfolders:
            print(f"No data folders found inside '{ROOT_DATASET_FOLDER}'.")
        else:
            print(f"Found {len(subfolders)} folders to process.")
            for folder in subfolders:
                process_folder(folder)
            print(f"\n{'='*80}\nBatch processing complete.\n{'='*80}")
