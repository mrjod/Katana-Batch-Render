import re
import tkinter as tk
from tkinter import ttk,filedialog
import subprocess
import threading
import psutil
import os
import customtkinter
import tkinterDnD
from PIL import Image
import queue
from functools import partial


command = "" 
render_thread = None
progressbar = None

katana_bin = "katanaBin.exe"
render_process = None
stop_render_event = threading.Event()
# Use CustomTkinter theme
customtkinter.set_ctk_parent_class(tkinterDnD.Tk)
# customtkinter.set_appearance_mode(change_appearance_mode_event)  # Modes: system (default), light, dark
customtkinter.set_default_color_theme("blue")  # Themes: blue (default), dark-blue, green

width = 900
height = 630
# GUI setup
root = customtkinter.CTk()
root.geometry(f"{width}x{height}")
root.title("Katana Batch Renderer")
root.grid_rowconfigure(0, weight=1)

render_output_queue = queue.Queue()

root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=100)


root.resizable(True, True)

# Global variables to track rendered frames
frame_range_list = []
completed_frames = set()

def parse_frame_range(frame_range_str):
    frames = set()
    for part in frame_range_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            frames.update(range(start, end + 1))
        else:
            frames.add(int(part))
    return frames

def render_frames():
    global render_process
    global progressbar  # Make sure progressbar is a global variable
    global render_thread  # Declare render_thread as a global variable
    global command  # Use the global command variable
    global frame_range_list
    global completed_frames
    
    katana_file = entry_katana_file.get()
    frame_range = entry_frame_range.get()
    render_node = entry_render_node.get()
    # Reset progress bar
    progressbar.set(0)
    completed_frames.clear()
    if not katana_file or not frame_range:
        #result_label.configure(text="Please provide Katana File and Frame Range.")
        result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
        result_label.delete(1.0, tk.END)  # Clear existing text
        result_label.insert(tk.END, "Please provide Katana File and Frame Range.")
        result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox
        return
    
    frame_range_list = parse_frame_range(frame_range)
    command = f'"{katana_bin}" --batch --katana-file="{katana_file}" -t {frame_range}'

    if render_node:
        command += f' --render-node={render_node}'

    # Add GSVs to the command
    for gsv in gsv_entries:
        name, value = gsv[0].get(), gsv[1].get()
        if name and value:
            command += f' --var {name}={value}'
    
    

    try:
        render_process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True) # Update this line
        # Redirect the output to a pipe to capture it
        if render_process:
            stop_render_button.configure(state=tk.NORMAL)
            render_thread = threading.Thread(target=monitor_render_output, args=(render_process,))
            render_thread.start()
            # threading.Thread(target=update_progress_from_process, args=(render_process, progressbar)).start()
            render_button.configure(state=tk.DISABLED)
        else:
            raise RuntimeError("Failed to start render process.")
    

    except Exception as e:
        #result_label.configure(text=f"Error: {e}")
        # print(f"Error starting rendering process: {e}")
        result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
        result_label.delete(1.0, tk.END)  # Clear existing text
        result_label.insert(tk.END, f"Error: {e}")
        result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox
    finally:
        stop_render_event.clear()
        
def update_progress_from_process(process, progressbar):
    try:
        for line in iter(process.stdout.readline, b''):
            update_progress(line, progressbar)
    except Exception as e:
        print(f"Error reading output: {e}")
    finally:
        process.stdout.close()
def render_frames_thread():
    global render_process
    global progressbar
    global stop_render_event

    # ... (Your existing rendering code)

    try:
        render_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,text=True, bufsize=1, universal_newlines=True)

        for line in iter(render_process.stdout.readline, b''):
            render_output_queue.put(line)
            root.after(10, update_progress, line, progressbar)

        render_thread = threading.Thread(target=monitor_render_output, args=(render_output_queue, progressbar, render_process.stdout))
        render_thread.start()

        # ... (Your existing code)

    except Exception as e:
        # print(f"Error starting rendering process: {e}")
        result_label.configure(state=tk.NORMAL)
        result_label.delete(1.0, tk.END)
        result_label.insert(tk.END, f"Error: {e}")
        result_label.configure(state=tk.DISABLED)
    finally:
        stop_render_event.set()
        stop_render_button.configure(state=tk.DISABLED)

def monitor_render_output(process):
# def monitor_render_output(output_stream):
    global render_process
    global progressbar
    global stop_render_event
    global frame_range_list
    def read_output(pipe, output_func):
        for line in iter(pipe.readline, ''):
            output_func(line)
    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, handle_stdout))
    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, handle_stderr))
    stdout_thread.start()
    stderr_thread.start()
    stdout_thread.join()
    stderr_thread.join()
    
    process.stdout.close()
    process.stderr.close()
    
    stop_render_event.set()
    render_button.configure(state=tk.NORMAL)
    stop_render_button.configure(state=tk.DISABLED)
    result_label.configure(state=tk.NORMAL)
    result_label.delete(1.0, tk.END)
    result_label.insert(tk.END, "Rendering Done!")
    result_label.configure(state=tk.DISABLED)
            
    # try:
    #     for line in iter(partial(output_stream.readline, 4096), ''):
    #         # print(line.strip())  # Debug: Print each line of output
    #         output_text.insert(tk.END, line)
    #         output_text.yview(tk.END) 
    #         update_progress(line, progressbar)
    #         check_frame_completion(line)
        
        # if completed_frames >= frame_range_list:
        #     stop_render_event.set()
            
        #     # Terminate the render process if it's still running
        #     if render_process and render_process.poll() is None:
        #         render_process.terminate()
        #         render_process.wait()  # Wait for the process to finish
        #         render_button.configure(state=tk.NORMAL)
        #         stop_render_button.configure(state=tk.DISABLED)
        #         result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
        #         result_label.delete(1.0, tk.END) 
        #         result_label.insert(tk.END, "Rendering Done!")
        #         result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox
            


    # except Exception as e:
    #     print(f"Error reading output: {e}")
    # finally:
    #     if not output_stream.closed:
    #         output_stream.close()
        
    #     # if completed_frames >= frame_range_list:
    #     stop_render_event.set()
    #     render_button.configure(state=tk.NORMAL)
    #     stop_render_button.configure(state=tk.DISABLED)
    #     result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
    #     result_label.delete(1.0, tk.END) 
    #     result_label.insert(tk.END, "Rendering Done!")
    #     result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox

def handle_stdout(line):
    output_text.insert(tk.END, line)
    output_text.yview(tk.END)
    update_progress(line, progressbar)
    check_frame_completion(line)

def handle_stderr(line):
    output_text.insert(tk.END, line)
    output_text.yview(tk.END)
                
def check_frame_completion(output_line):
    match = re.search(r"Frame (\d+) completed", output_line)
    if match:
        frame = int(match.group(1))
        completed_frames.add(frame)
        result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
        result_label.delete(1.0, tk.END) 
        result_label.insert(tk.END, f"Frame {frame} completed")
        result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox
        update_result_label()
def update_result_label():
    completed_frames_str = ", ".join(map(str, sorted(completed_frames)))
    #result_label.configure(text=f"Completed frames: {completed_frames_str}")
    result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
    result_label.delete(1.0, tk.END) 
    result_label.insert(tk.END, f"Frame {completed_frames_str} completed")
    result_label.configure(state=tk.DISABLED)
        
def update_ui(output_queue):
    try:
        while True:
            message = output_queue.get()
            if not message:
                break
            output_text.insert(tk.END, message + "\n")
            output_text.yview(tk.END)  # Auto-scroll to the end

    except Exception as e:
        print(f"Error updating UI: {e}")
def update_output_text(line):
    output_text.configure(state=tk.NORMAL)
    output_text.insert(tk.END, line)
    output_text.see(tk.END)
    output_text.configure(state=tk.DISABLED)
    output_text.update_idletasks()
# Add this function to update the progress bar based on the output
# Add this function to update the progress bar based on the output
def update_progress(output_line, progressbar):
    # Search for the percentage in the output line
    if "done -" in output_line and "%" in output_line:
        try:
            # Extract the percentage value
            percentage = int(output_line.split("%")[0].split()[-1])
            # Convert the percentage to a value between 0 and 1
            progress = percentage / 100.0
            # Update the progress bar
            progressbar.set(progress)
            # print(f"Updated progress to {progress}")
        except ValueError:
            pass  # Handle the case where the conversion to int fail

def _update_progress(output_line, progressbar):
    # Search for the percentage in the output line
    if "done -" in output_line and "%" in output_line:
        try:
            # Extract the percentage value
            percentage = int(output_line.split("%")[0].split()[-1])
            # Convert the percentage to a value between 0 and 1
            progress = percentage / 100.0
            # Update the progress bar
            progressbar.set(progress)
            # print(f"Updated progress to {progress}")
        except ValueError:
            pass  # Handle the case where the conversion to int fails
       
def extract_progress_from_line(line):
    # Add your logic to extract the progress value from the line
    # For example, you might use regular expressions to find the progress value
    # Customize this based on the format of your render output
    progress_match = re.search(r"Progress: (\d+)%", line)
    if progress_match:
        return int(progress_match.group(1)) / 100.0
    else:
        return 0.0
    

# Bind the cleanup function to the UI close event
def cleanup_on_close():
    global render_process
    
    if render_thread and render_thread.is_alive():
        render_thread.join(timeout=0)
        stop_render()
    elif render_process and render_process.poll() is None:
        stop_render()
    if render_process:
        try:
            parent = psutil.Process(render_process.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()

            parent.terminate()
            parent.wait()  # Wait for the parent process to finish
            #result_label.configure(text="Batch rendering stopped.")
            result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
            result_label.delete(1.0, tk.END)  # Clear existing text
            result_label.insert(tk.END, "Batch rendering stopped.")
            result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox
        except Exception as e:
            #result_label.configure(text=f"Error stopping render: {e}")
            result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
            result_label.delete(1.0, tk.END)  # Clear existing text
            result_label.insert(tk.END, f"Error stopping render: {e}")
            result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox
    # root.protocol("WM_DELETE_WINDOW", cleanup_on_close)
    root.destroy()
    
def display_output(output_stream):
    print("Displaying output")
    for line in output_stream:
        # Update the CTkText widget with the command output
        root.after(10, output_text.insert, tk.END, line)

    output_stream.close()
    
def stop_render():
    global render_process
    global stop_render_event
    if render_process:
        try:
            if psutil.pid_exists(render_process.pid):
                parent = psutil.Process(render_process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()

                parent.terminate()
                parent.wait()
                result_label.configure(state=tk.NORMAL)
                result_label.delete(1.0, tk.END)
                result_label.insert(tk.END, "Batch rendering stopped.")
                result_label.configure(state=tk.DISABLED)
            else:
                result_label.configure(state=tk.NORMAL)
                result_label.delete(1.0, tk.END)
                result_label.insert(tk.END, "Batch rendering process not found.")
                result_label.configure(state=tk.DISABLED)

        except Exception as e:
            result_label.configure(state=tk.NORMAL)
            result_label.delete(1.0, tk.END)
            result_label.insert(tk.END, f"Error stopping render: {e}")
            result_label.configure(state=tk.DISABLED)
        finally:
            render_button.configure(state=tk.NORMAL)
            stop_render_button.configure(state=tk.DISABLED)
            stop_render_event.set()

def monitor_render_process(process):
    global render_process
    global progressbar
    global stop_render_event
    
    
    # while True:
    #     if stop_render_event.is_set():
    #         break

    #     line = process.stdout.readline()
    #     if line:
    #         render_output_queue.put(line)
    #         root.after(100, update_output_text, line)
    #         check_frame_completion(line)
    #     else:
    #         break
    # # After processing all output, check if all frames are completed
    # if completed_frames >= frame_range_list:
    #     stop_render_event.set()  # Signal to stop rendering
    #     render_button.configure(state=tk.NORMAL)  # Enable render button
    #     stop_render_button.configure(state=tk.DISABLED)  # Disable stop render button
    #     result_label.configure(state=tk.NORMAL)  # Enable result label
    #     result_label.delete(1.0, tk.END)  # Clear existing text
    #     result_label.insert(tk.END, "Rendering Done!")  # Update rendering status
    #     result_label.configure(state=tk.DISABLED)  # Disable result label

    # # After checking completion, close the output stream
    # process.stdout.close()
    
    
     #global stop_render_event
    process.communicate()  # Wait for the process to finish
    stop_render_event.set()  # Signal that the rendering process has finished
    stop_render_button.configure(state=tk.DISABLED)  # Disable the stop render button

def browse_katana_file():
    file_path = filedialog.askopenfilename(filetypes=[("Katana Files", "*.katana")])
    entry_katana_file.delete(0, tk.END)
    entry_katana_file.insert(0, file_path)
    
def save_preset():
    katana_file = entry_katana_file.get()
    frame_range = entry_frame_range.get()
    render_node = entry_render_node.get()

    if not katana_file or not frame_range:
        result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
        result_label.delete(1.0, tk.END)  # Clear existing text
        result_label.insert(tk.END, "Cannot save preset without Katana File and Frame Range.")
        result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox
        #result_label.configure(text="Cannot save preset without Katana File and Frame Range.")
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
        #result_label.configure(text=f"Preset saved to {preset_name}")
        result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
        result_label.delete(1.0, tk.END)  # Clear existing text
        result_label.insert(tk.END, f"Preset saved to {preset_name}")
        result_label.configure(state=tk.DISABLED)  # Disable the CTkTextbox

def load_katana_bin():
    global katana_bin
    katana_bin = filedialog.askopenfilename(filetypes=[("Batch Files", "*.bat")])
    result_label.configure(text=f"KatanaBin.exe loaded from: {katana_bin}")

def load_preset():
    global katana_bin
    # Clear existing GSV entries
    for entry in gsv_entries:
        entry[0].destroy()
        entry[1].destroy()
        entry[2].destroy()

    # Clear the list of GSV entries
    gsv_entries.clear()
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
                result_label.configure(state=tk.NORMAL)  # Allow modifications
                result_label.delete("1.0", tk.END)  # Clear existing text
                result_label.insert(tk.END, f".bat file loaded from preset: {katana_bin}")  # Add new text
                result_label.configure(state=tk.DISABLED)  # Disable modifications
            else:
                katana_bin = "katanaBin.exe"
                entry_load_bat.delete(0, tk.END)  # Clear the .bat file path
                result_label.configure(state=tk.NORMAL)  # Allow modifications
                result_label.delete("1.0", tk.END)  # Clear existing text
                result_label.insert(tk.END, "Using default KatanaBin.exe")  # Add new text
                result_label.configure(state=tk.DISABLED)  # Disable modifications

def add_gsv_entry(name=None, value=None):
    # Create or use an existing scrollable frame
    gsv_name_entry = customtkinter.CTkEntry(gsv_frame, height=30, width=100, placeholder_text="Var")
    gsv_name_entry.grid(row=len(gsv_entries) + 1, column=0, padx=10, pady=(5, 5), sticky="nsew")

    gsv_value_entry = customtkinter.CTkEntry(gsv_frame, height=20, width=100, placeholder_text="Value")
    gsv_value_entry.grid(row=len(gsv_entries) + 1, column=1, padx=10, pady=(5, 5), sticky="nsew")

    remove_button = customtkinter.CTkButton(gsv_frame, text="Remove", width=100, height=24, command=lambda: remove_gsv_entry(gsv_name_entry, gsv_value_entry, remove_button))
    remove_button.grid(row=len(gsv_entries) + 1, column=2, padx=5, pady=(5, 5), sticky="nsew")

    gsv_entries.append((gsv_name_entry, gsv_value_entry, remove_button))
    
    # Set the values if provided
    if name is not None and value is not None:
        gsv_name_entry.insert(0, name)
        gsv_value_entry.insert(0, value)
            
            
            
    # gsv_name_entry = customtkinter.CTkFrame(gsv_frame, width=15)
    # #gsv_name_entry = tk.Entry(gsv_frame, width=15)
    # gsv_name_entry.grid(row=0, column=0, padx=5)

    # gsv_value_entry = customtkinter.CTkFrame(gsv_frame, width=15)
    # #gsv_value_entry = tk.Entry(gsv_frame, width=15)
    # gsv_value_entry.grid(row=0, column=1, padx=5)

    # remove_button = tk.Button(gsv_frame, text="Remove", command=lambda frame=gsv_frame: remove_gsv_entry(frame))
    # remove_button.grid(row=0, column=2, padx=5)

    # gsv_entries.append((gsv_name_entry, gsv_value_entry, gsv_frame))

    # # Set the values if provided
    # if name is not None and value is not None:
    #     gsv_name_entry.insert(0, name)
    #     gsv_value_entry.insert(0, value)

def remove_gsv_entry(gsv_name_entry, gsv_value_entry, remove_button):
    # Remove the GSV entry and destroy associated widgets
    gsv_entries.remove((gsv_name_entry, gsv_value_entry, remove_button))
    gsv_name_entry.destroy()
    gsv_value_entry.destroy()
    remove_button.destroy()
    
    
def load_bat_file():
    global katana_bin
    bat_file_path = entry_load_bat.get()

    if bat_file_path:
        katana_bin = bat_file_path
        # result_label.configure(text=f"KatanaBin.exe loaded from: {katana_bin}")
        result_label.configure(state=tk.NORMAL)  # Allow modifications
        result_label.delete("1.0", tk.END)  # Clear existing text
        result_label.insert(tk.END, f"KatanaBin.exe loaded from: {katana_bin}")  # Add new text
        result_label.configure(state=tk.DISABLED)  # Disable modifications
    else:
        katana_bin = "katanaBin.exe"
        # result_label.configure(text=f"Using default KatanaBin.exe")
        result_label.configure(state=tk.NORMAL)  # Allow modifications
        result_label.delete("1.0", tk.END)  # Clear existing text
        result_label.insert(tk.END, "Using default KatanaBin.exe")  # Add new text
        result_label.configure(state=tk.DISABLED)  # Disable modifications

def change_appearance_mode_event(new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)





# # GUI setup
# root = customtkinter.CTk()

# root.title("Katana Batch Renderer")
# root.resizable(False, False)

# Set custom icon
icon_path = "WindowsIcon.ico"  # Replace with the path to your .ico file
root.iconbitmap(icon_path)

# # load and create background image
# current_path = os.path.dirname(os.path.realpath(__file__))
# bg_image = customtkinter.CTkImage(Image.open( r"C:\Users\jomil\Downloads\CustomTkinter-master\examples\test_images\bg_gradient.jpg"),
#                                                size=(width, height))
# bg_image_label = customtkinter.CTkLabel(master=root, image=bg_image)
# bg_image_label.grid(row=0, column=0)

# create sidebar frame with widgets
sidebar_frame = customtkinter.CTkFrame(master=root, width=140, corner_radius=0)
sidebar_frame.grid(row=0, column=0, rowspan=10, sticky="NWSE")
sidebar_frame.grid_rowconfigure(0, weight=1)
sidebar_frame.grid_columnconfigure(1, weight=1)

my_image = customtkinter.CTkImage(light_image=Image.open("WindowsIcon.ico"),
                                  dark_image=Image.open("WindowsIcon.ico"),
                                  size=(60, 60))

image_label = customtkinter.CTkLabel(sidebar_frame, image=my_image, text="",)  # display image with a CTkLabel
image_label.grid(row=0, column=0, pady= 30,padx= 10, sticky="NW")

# create Main frame with widgets
Mainbar_frame = customtkinter.CTkFrame(master=root,height=900, width=1000, corner_radius=0, fg_color="transparent")
Mainbar_frame.grid(row=0, column=1, rowspan=1, sticky="NWSE")
Mainbar_frame.grid_columnconfigure(0, weight=1,minsize= 200)
Mainbar_frame.grid_columnconfigure(1, weight=10,minsize= 200)
Mainbar_frame.grid_columnconfigure(2, weight=10,minsize= 200)
Mainbar_frame.grid_columnconfigure(3, weight=1,minsize= 200)


Mainbar_frame.grid_rowconfigure(5, weight=1)
Mainbar_frame.grid_rowconfigure(6, weight=1)
Mainbar_frame.grid_rowconfigure(7, weight=1)
Mainbar_frame.grid_rowconfigure(8, weight=1)
Mainbar_frame.grid_rowconfigure(9, weight=50)


secondbar_frame = customtkinter.CTkFrame(master=root,height=1000, width=100, corner_radius=0, fg_color="transparent")
secondbar_frame.grid(row=1, column=1, rowspan=5,  sticky="NWSE")
secondbar_frame.grid_columnconfigure(0, weight=1,minsize= 200)
secondbar_frame.grid_columnconfigure(1, weight=1,minsize= 200)

# create Footer frame with widgets
footer_frame = customtkinter.CTkFrame(master=root, corner_radius=0, fg_color="transparent" )
footer_frame.grid(row=12, column=0, columnspan=2,   sticky="NWSE")
footer_frame.grid_rowconfigure(0, weight=50)
footer_frame.grid_rowconfigure(1, weight=1)
footer_frame.grid_columnconfigure(0, weight=1)
footer_frame.grid_columnconfigure(1, weight=1)
footer_frame.grid_columnconfigure(2, weight=2)





#apperance window

appearance_mode_label = customtkinter.CTkLabel(master=sidebar_frame, text="Appearance Mode:", anchor="w")
appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
appearance_mode_optionemenu = customtkinter.CTkOptionMenu(master=sidebar_frame, values=["Light", "Dark", "System"],
                                                                       command=change_appearance_mode_event)
appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))
# Set the default value (for example, "Light")
appearance_mode_optionemenu.set("System")
# Katana File input

label_katana_file = customtkinter.CTkLabel(master=Mainbar_frame, anchor="w", text="Katana File:")
label_katana_file.grid(row=1, column=0, padx=(50, 0), pady=5, sticky="nsew")
entry_katana_file = customtkinter.CTkEntry(master=Mainbar_frame, placeholder_text="Browse to the Directory of your .Katana file")
entry_katana_file.grid(row=1, column=1, columnspan=2, padx=(20, 0), pady=(5, 5), sticky="nsew")
#btn_browse_katana_file = tk.Button(root, text="Browse", command=browse_katana_file,)
btn_browse_katana_file = customtkinter.CTkButton(master=Mainbar_frame, text="Browse", command=browse_katana_file)
btn_browse_katana_file.grid(row=1, column=3, padx=10, pady=5, sticky="W")

# Frame Range input
label_frame_range = customtkinter.CTkLabel(master=Mainbar_frame, anchor="w", text="Frame Range:")
label_frame_range.grid(row=2, column=0, padx=(50, 0), pady=5, sticky="nsew")
entry_frame_range = customtkinter.CTkEntry(master=Mainbar_frame, placeholder_text="1-3,5-10")
entry_frame_range.grid(row=2, column=1, columnspan=2, padx=(20, 0), pady=(5, 5), sticky="nsew")


# Render Node input
label_render_node = customtkinter.CTkLabel(master=Mainbar_frame, justify=customtkinter.LEFT, text="Render Node (optional):")
label_render_node.grid(row=3, column=0, padx=(50, 0), pady=(5, 50), sticky="W")

entry_render_node = customtkinter.CTkEntry(master=Mainbar_frame, placeholder_text="Enter the node to render from")
entry_render_node.grid(row=3, column=1, columnspan=2, padx=(20, 0), pady=(5, 50), sticky="nsew")



# Load .bat file input
label_load_bat = customtkinter.CTkLabel(master=Mainbar_frame, anchor="w", text=".bat File:(Optional)")
label_load_bat.grid(row=0, column=0, padx=(50, 0),pady=(50, 0), sticky="W")
entry_load_bat = customtkinter.CTkEntry(master=Mainbar_frame, placeholder_text="Select Batch launcher")
entry_load_bat.grid(row=0, column=1, columnspan=2, padx=(20, 0), pady=(50, 5), sticky="nsew")
btn_browse_bat = customtkinter.CTkButton(master=Mainbar_frame, text="Browse", command=lambda: entry_load_bat.insert(tk.END, filedialog.askopenfilename(filetypes=[("Batch Files", "*.bat")])))
#btn_browse_bat = tk.Button(root, text="Browse", command=lambda: entry_load_bat.insert(tk.END, filedialog.askopenfilename(filetypes=[("Batch Files", "*.bat")])))
btn_browse_bat.grid(row=0, column=3, pady=(50, 0), padx=(10, 5),sticky="WN")

# Load .bat file button
load_bat_button = customtkinter.CTkButton(master=Mainbar_frame, text="Load .bat File", command=load_bat_file)
#load_bat_button = tk.Button(root, text="Load .bat File", command=load_bat_file)
load_bat_button.grid(row=0, column=4, pady=(50, 0), padx=(5, 50),sticky="WN")

# Render button
render_button = customtkinter.CTkButton(master=secondbar_frame, text="Render Frames", command=render_frames)
#render_button = tk.Button(root, text="Render Frames", command=render_frames)
render_button.grid(row=10, column=3, padx=(5, 10),  pady=10,sticky="nsew")

# Stop render button
stop_render_button = customtkinter.CTkButton(master=secondbar_frame, text="Stop Render", command=stop_render, state=tk.DISABLED)
#stop_render_button = tk.Button(root, text="Stop Render", command=stop_render, state=tk.DISABLED)
stop_render_button.grid(row=10, column=4, padx=(5, 50), pady=10,sticky="nsew")

# Save Preset button
save_preset_button = customtkinter.CTkButton(master=sidebar_frame,width=5, text="Save Preset", command=save_preset)
#save_preset_button = tk.Button(root, text="Save Preset", command=save_preset)
save_preset_button.grid(row=3, column=0, pady=(20,5), padx=(10, 10),sticky="N")

# Load Preset button
load_preset_button = customtkinter.CTkButton(master=sidebar_frame, width=5, text="Load Preset", command=load_preset)
#load_preset_button = tk.Button(root, text="Load Preset", command=load_preset)
load_preset_button.grid(row=4, column=0, pady=(5,10), padx=(10, 10), sticky="N")


# emptyResult label
emptyresult_label = customtkinter.CTkLabel(footer_frame, text="Output:   ", font=('Arial', 11))
emptyresult_label.grid(row=0, column=1, pady=1, sticky="E")  

# Result label
result_label = customtkinter.CTkTextbox(footer_frame, wrap=tk.WORD, height=3, width=10, font=('Arial', 11))
result_label.grid(row=0, column=2, padx=20,  pady=5, sticky="nsew")

# GSV Frame container
gsv_frame_container = customtkinter.CTkFrame(master=Mainbar_frame,height=100, width=100, corner_radius=0)
#gsv_frame_container = tk.Frame(root)
gsv_frame_container.grid(row=5, column=0, columnspan=4,  pady=10,padx=(50,0), sticky="nsew")
gsv_frame_container.grid_rowconfigure(0, weight=1, )
gsv_frame_container.grid_columnconfigure(0, weight=1 )
gsv_frame_container.grid_rowconfigure(1, weight=50)
# GSV Entries
gsv_entries = []


# Add GSV button
add_gsv_button = customtkinter.CTkButton(master=Mainbar_frame, text="Add GSV Entry", command=add_gsv_entry)
#add_gsv_button = tk.Button(root, text="Add GSV Entry", command=add_gsv_entry)
add_gsv_button.grid(row=5, column=4, pady=10, padx=(0, 50), sticky="N")

# Output text widget
output_text = customtkinter.CTkTextbox(master=secondbar_frame, wrap=tk.WORD, height=100, width=50)
output_text.grid(row=9, column=0, columnspan=5, padx=40, pady=40, sticky="nsew")
output_text.configure(state=tk.NORMAL)  # Allow modifications
root.protocol("WM_DELETE_WINDOW", cleanup_on_close)

progressbar = customtkinter.CTkProgressBar(secondbar_frame, orientation="horizontal")
progressbar.grid(row=10, column=0, padx=(20, 10), pady=(10, 10), sticky="ew")
progressbar.set(0)
# Footer label
footer_label = customtkinter.CTkLabel(footer_frame, height=10,  text= "This Script was written by Oluwajomiloju Osho with the help of ChatGPT", font=('Arial', 8),)

footer_label.grid(row=0, column=0, padx=10, pady=10,sticky="W")


# Initialize the GSV frame outside the add_gsv_entry function
gsv_frame = customtkinter.CTkScrollableFrame(master=gsv_frame_container, width=10, corner_radius=0,label_text="Graph state variables", orientation='vertical')
gsv_frame.grid(row=0, column=0, padx=0, pady=0, sticky="EW")
gsv_frame.grid_columnconfigure(0, weight=3)
gsv_frame.grid_columnconfigure(1, weight=3)
gsv_frame.grid_columnconfigure(2, weight=1)
gsv_frame.grid_rowconfigure(0, weight=1)  # Adjust the weight

root.protocol("WM_DELETE_WINDOW", cleanup_on_close)
root.mainloop()
