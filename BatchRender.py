import tkinter as tk
from tkinter import filedialog
import subprocess
import threading
import psutil


katana_bin = "katanaBin.exe"
render_process = None
stop_render_event = threading.Event()

def render_frames():
    global render_process
    katana_file = entry_katana_file.get()
    frame_range = entry_frame_range.get()
    render_node = entry_render_node.get()

    if not katana_file or not frame_range:
        result_label.config(text="Please provide Katana File and Frame Range.")
        return

    command = f'"{katana_bin}" --batch --katana-file="{katana_file}" -t {frame_range}'

    if render_node:
        command += f' --render-node={render_node}'

    # Add GSVs to the command
    for gsv in gsv_entries:
        name, value = gsv[0].get(), gsv[1].get()
        if name and value:
            command += f' --var {name}={value}'

    try:
        render_process = subprocess.Popen(command, shell=True)
        result_label.config(text="Batch rendering started.")
        stop_render_button.config(state=tk.NORMAL)  # Enable the stop render button

        # Monitor the process in a separate thread
        monitor_thread = threading.Thread(target=monitor_render_process, args=(render_process,))
        monitor_thread.start()

    except Exception as e:
        result_label.config(text=f"Error: {e}")

def stop_render():
    global render_process
    if render_process:
        try:
            parent = psutil.Process(render_process.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()

            parent.terminate()
            parent.wait()  # Wait for the parent process to finish
            result_label.config(text="Batch rendering stopped.")
        except Exception as e:
            result_label.config(text=f"Error stopping render: {e}")

def monitor_render_process(process):
    global stop_render_event
    process.communicate()  # Wait for the process to finish
    stop_render_event.set()  # Signal that the rendering process has finished
    stop_render_button.config(state=tk.DISABLED)  # Disable the stop render button

def browse_katana_file():
    file_path = filedialog.askopenfilename(filetypes=[("Katana Files", "*.katana")])
    entry_katana_file.delete(0, tk.END)
    entry_katana_file.insert(0, file_path)
    
def save_preset():
    katana_file = entry_katana_file.get()
    frame_range = entry_frame_range.get()
    render_node = entry_render_node.get()

    if not katana_file or not frame_range:
        result_label.config(text="Cannot save preset without Katana File and Frame Range.")
        return

    preset_name = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])

    if preset_name:
        with open(preset_name, 'w') as file:
            file.write(f"Katana File: {katana_file}\n")
            file.write(f"Frame Range: {frame_range}\n")
            if render_node:
                file.write(f"Render Node: {render_node}\n")
            for gsv in gsv_entries:
                name, value = gsv[0].get(), gsv[1].get()
                if name and value:
                    file.write(f"GSV: {name}={value}\n")
            if katana_bin:
                file.write(f"Bat File: {katana_bin}\n")
        result_label.config(text=f"Preset saved to {preset_name}")

def load_katana_bin():
    global katana_bin
    katana_bin = filedialog.askopenfilename(filetypes=[("Batch Files", "*.bat")])
    result_label.config(text=f"KatanaBin.exe loaded from: {katana_bin}")

def load_preset():
    global katana_bin
    preset_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])

    if preset_path:
        with open(preset_path, 'r') as file:
            loaded_katana_bin = None
            for line in file:
                if line.startswith("Katana File:"):
                    entry_katana_file.delete(0, tk.END)
                    entry_katana_file.insert(0, ":".join(line.split(":")[1:]).strip())
                elif line.startswith("Frame Range:"):
                    entry_frame_range.delete(0, tk.END)
                    entry_frame_range.insert(0, line.split(":")[1].strip())
                elif line.startswith("Render Node:"):
                    entry_render_node.delete(0, tk.END)
                    entry_render_node.insert(0, line.split(":")[1].strip())
                elif line.startswith("GSV:"):
                    parts_gsv = line.split(":")[1].strip().split("=")
                    if len(parts_gsv) == 2:
                        add_gsv_entry(parts_gsv[0], parts_gsv[1])
                elif line.startswith("Bat File:"):  # Check for .bat file in the preset
                    loaded_katana_bin = ":".join(line.split(":")[1:]).strip()

            if loaded_katana_bin:
                katana_bin = loaded_katana_bin
                entry_load_bat.delete(0, tk.END)
                entry_load_bat.insert(0, katana_bin)
                load_bat_file()
                result_label.config(text=f".bat file loaded from preset: {katana_bin}")
            else:
                katana_bin = "katanaBin.exe"
                entry_load_bat.delete(0, tk.END)  # Clear the .bat file path
                result_label.config(text="Using default KatanaBin.exe")

def add_gsv_entry(name=None, value=None):
    gsv_frame = tk.Frame(gsv_frame_container)
    gsv_frame.grid(row=len(gsv_entries) + 1, column=0, pady=5, sticky=tk.W)

    gsv_name_entry = tk.Entry(gsv_frame, width=15)
    gsv_name_entry.grid(row=0, column=0, padx=5)

    gsv_value_entry = tk.Entry(gsv_frame, width=15)
    gsv_value_entry.grid(row=0, column=1, padx=5)

    remove_button = tk.Button(gsv_frame, text="Remove", command=lambda frame=gsv_frame: remove_gsv_entry(frame))
    remove_button.grid(row=0, column=2, padx=5)

    gsv_entries.append((gsv_name_entry, gsv_value_entry, gsv_frame))

    # Set the values if provided
    if name is not None and value is not None:
        gsv_name_entry.insert(0, name)
        gsv_value_entry.insert(0, value)

def remove_gsv_entry(frame):
    frame.destroy()

    # Find and remove the corresponding entry from gsv_entries
    for entry in gsv_entries:
        if entry[2] == frame:
            gsv_entries.remove(entry)
            break

def load_bat_file():
    global katana_bin
    bat_file_path = entry_load_bat.get()

    if bat_file_path:
        katana_bin = bat_file_path
        result_label.config(text=f"KatanaBin.exe loaded from: {katana_bin}")
    else:
        katana_bin = "katanaBin.exe"
        result_label.config(text=f"Using default KatanaBin.exe")


# GUI setup
root = tk.Tk()
root.title("Katana Batch Renderer")

# Set custom icon
icon_path = "jomilojuArnold222.ico"  # Replace with the path to your .ico file
root.iconbitmap(icon_path)

# Katana File input
label_katana_file = tk.Label(root, text="Katana File:")
label_katana_file.grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
entry_katana_file = tk.Entry(root, width=50)
entry_katana_file.grid(row=0, column=1, padx=10, pady=10, columnspan=2)
btn_browse_katana_file = tk.Button(root, text="Browse", command=browse_katana_file)
btn_browse_katana_file.grid(row=0, column=3, padx=10, pady=10)

# Frame Range input
label_frame_range = tk.Label(root, text="Frame Range:")
label_frame_range.grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
entry_frame_range = tk.Entry(root, width=20)
entry_frame_range.grid(row=1, column=1, padx=10, pady=10)

# Render Node input
label_render_node = tk.Label(root, text="Render Node (optional):")
label_render_node.grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
entry_render_node = tk.Entry(root, width=20)
entry_render_node.grid(row=2, column=1, padx=10, pady=10)

# Load .bat file input
label_load_bat = tk.Label(root, text=".bat File:")
label_load_bat.grid(row=3, column=0, pady=10, padx=(10, 0), sticky=tk.W)
entry_load_bat = tk.Entry(root, width=50)
entry_load_bat.grid(row=3, column=1, pady=10, padx=(0, 10), columnspan=2)
btn_browse_bat = tk.Button(root, text="Browse", command=lambda: entry_load_bat.insert(tk.END, filedialog.askopenfilename(filetypes=[("Batch Files", "*.bat")])))
btn_browse_bat.grid(row=3, column=3, pady=10, padx=(0, 10))

# Load .bat file button
load_bat_button = tk.Button(root, text="Load .bat File", command=load_bat_file)
load_bat_button.grid(row=3, column=4, pady=10, padx=(0, 10))

# Render button
render_button = tk.Button(root, text="Render Frames", command=render_frames)
render_button.grid(row=4, column=0, columnspan=4, pady=10)

# Stop render button
stop_render_button = tk.Button(root, text="Stop Render", command=stop_render, state=tk.DISABLED)
stop_render_button.grid(row=4, column=4, pady=10)

# Save Preset button
save_preset_button = tk.Button(root, text="Save Preset", command=save_preset)
save_preset_button.grid(row=5, column=0, pady=10, padx=(10, 0))

# Load Preset button
load_preset_button = tk.Button(root, text="Load Preset", command=load_preset)
load_preset_button.grid(row=5, column=1, pady=10, padx=(0, 10))

# Add GSV button
add_gsv_button = tk.Button(root, text="Add GSV Entry", command=add_gsv_entry)
add_gsv_button.grid(row=5, column=2, pady=10, padx=(0, 10))

# Result label
result_label = tk.Label(root, text="")
result_label.grid(row=6, column=0, columnspan=4, pady=10)

# GSV Frame container
gsv_frame_container = tk.Frame(root)
gsv_frame_container.grid(row=7, column=0, columnspan=4, pady=10)

# GSV Entries
gsv_entries = []

# Footer label
footer_label = tk.Label(root, text="This Script was written by Oluwajomiloju Osho with the help of ChatGPT", font=('Arial', 8), fg='gray')
footer_label.grid(row=8, column=0, columnspan=4, pady=10)

root.mainloop()
