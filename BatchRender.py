import re
import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import threading
import time
import psutil
import os
import customtkinter
from CTkListbox import *
import tkinterDnD
from PIL import Image   
import queue
from functools import partial


# Global variables
render_queue = queue.Queue()
current_render = None
stop_event = threading.Event()
pause_event = threading.Event()
current_render_item = None

# Initialize gsv_entries at the global level



command = "" 
render_thread = None
progressbar = None

katana_bin = "katanaBin"
render_process = None
error_detected = False
stop_render_event = threading.Event()
initial_frame_rendering_detected = False
rendering_stopped = False
new_appearance_mode = "Dark"
# Flag for enabling or disabling reuse rendering process
# reuse_rendering_process_enabled = False
initial_calculation_done = False  # Tracks if initial frame calculation phase is complete
manually_stopped = False


forgro_color="#1d1e1e"
gray_color= "gray"

gsv_entries = []
# Global variable to track enabled/disabled state of items
queue_item_states = []

# Initialize CustomTkinter
# customtkinter.set_ctk_parent_class(tkinterDnD.Tk)
# customtkinter.set_appearance_mode("Dark")
# customtkinter.set_default_color_theme("blue")

# Create main window
# width = 900
# height = 630
# root = customtkinter.CTk()
# root.geometry(f"{width}x{height}")
# root.title("Katana Batch Renderer")
# root.grid_rowconfigure(0, weight=1)

render_output_queue = queue.Queue()

# root.grid_columnconfigure(0, weight=1)
# root.grid_columnconfigure(1, weight=100)


# root.resizable(True, True)

# Global variables to track rendered frames
frame_range_list = []
completed_frames = set()

    
def parse_job_from_text(text):
    """Parses a job dictionary from the listbox item text."""
    try:
        parts = text.split(" | ")
        katana_file = parts[0].split(". ")[1]
        frame_range = parts[1].split(": ")[1]
        return {"katana_file": katana_file, "frame_range": frame_range}
    except Exception as e:
        print(f"Error parsing job: {e}")
        return None
    
def parse_frame_range(frame_range_str):
    frames = set()
    for part in frame_range_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            frames.update(range(start, end + 1))
        else:
            frames.add(int(part))
    return frames

def show_value(selected_option):
    result_label.configure(state=tk.NORMAL)  # Enable the CTkTextbox for editing
    result_label.delete(1.0, tk.END)  # Clear existing text
    result_label.insert(tk.END, f"Selected Option: {selected_option}")
    result_label.configure(state=tk.DISABLED)
    
# Draggable Treeview Class remains unchanged
class DraggableTreeview(ttk.Treeview):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.locked_indices = set()  # Set of indices that are permanently locked (rendered)
        self.currently_rendering_index = None  # Index currently being rendered
        self.bind('<ButtonPress-1>', self.on_drag_start)
        self.bind('<B1-Motion>', self.on_drag_motion)
        self.bind('<ButtonRelease-1>', self.on_drag_drop)
        self.dragged_item = None

    def on_drag_start(self, event):
        item = self.identify_row(event.y)
        if item:
            tags = self.item(item, 'tags')
            if 'rendering' in tags or 'rendered' in tags:
                return 'break'  # Prevent drag if item is rendering or rendered
            current_index = self.index(item)
            if current_index in self.locked_indices:
                return 'break'  # Prevent drag if item is locked
            if self.currently_rendering_index is not None and current_index <= self.currently_rendering_index:
                return 'break'  # Prevent drag if item is before or currently rendering
            self.dragged_item = item
            self.selection_set(item)

    def on_drag_motion(self, event):
        if self.dragged_item:
            item = self.identify_row(event.y)
            if item and item != self.dragged_item:
                target_index = self.index(item)
                dragged_index = self.index(self.dragged_item)
                if target_index in self.locked_indices:
                    return 'break'
                if self.currently_rendering_index is not None and target_index <= self.currently_rendering_index:
                    return 'break'
                self.move(self.dragged_item, '', target_index)

    def on_drag_drop(self, event):
        if self.dragged_item:
            item = self.identify_row(event.y)
            if item and item != self.dragged_item:
                target_index = self.index(item)
                dragged_index = self.index(self.dragged_item)
                if target_index in self.locked_indices:
                    return 'break'
                if self.currently_rendering_index is not None and target_index <= self.currently_rendering_index:
                    return 'break'
                self.move(self.dragged_item, '', target_index)
            self.dragged_item = None
            update_row_numbers(self)

def update_row_numbers(tree):
    items = tree.get_children()
    for index, item in enumerate(items, start=1):
        old_values = tree.item(item, "values")
        # just update the #0 text to new index
        tree.item(item, text=str(index), values=old_values)

# def on_render_button_click(tree):
#     global render_thread
#     render_thread = threading.Thread(target=lambda: render(tree))
#     render_thread.start()
def disable_header_click(event):
    region = event.widget.identify_region(event.x, event.y)
    if region == "heading":
        return "break"
       
def create_treeview(parent):
    style = ttk.Style()
    style.theme_use("default")
    
    style.configure("Custom.Treeview.Heading",
                background="#1d1e1e",      # sets header background to gray
                foreground="white",     # sets header text color (adjust as needed)
                font=("Arial", 16),
                borderwidth=0,
                relief="flat")     # sets header font size to 16

    
    style.map(
        "Custom.Treeview.Heading",
        background=[
            ("active", "#1d1e1e"),    # same color as normal
            ("pressed", "#1d1e1e")
        ],
        relief=[
            ("active", "flat"),
            ("pressed", "flat")
        ],
        foreground=[
            ("active", "white"),
            ("pressed", "white")
        ]
    )
    
    # Configure a custom style named "Custom.Treeview"
    
    style.configure(
        "Custom.Treeview",
        background="#2A2A2A",       # dark gray background
        fieldbackground="#2A2A2A",  # same background color for fields
        foreground="white",         # white text
        rowheight=25,               # slightly taller rows
        font=("Arial", 16),
        borderwidth=0,
        relief="flat"
        # bigger font to match the UI
    )
    # Optionally, change the highlight color for selected rows:
    style.map("Custom.Treeview",
              background=[("selected", "#1A1A1A")])

    tree = DraggableTreeview(
        parent,
        columns=("KatanaFile", "FrameRange", "RenderNode", "GSV", "Flags", "BatFile","Status", "KatanaFullPath", "BatFullPath", "Switch"),
        style="Custom.Treeview"
    )

    # #0 column will show your "ID"
    tree.heading("#0", text="ID", anchor="center")
    tree.column("#0", width=40, anchor="center", stretch=False)

    # 1) KatanaFile column
    tree.heading("KatanaFile", text="Katana File", anchor="center")
    tree.column("KatanaFile", width=180, anchor="center", stretch=True)

    # 2) FrameRange column
    tree.heading("FrameRange", text="Frame Range", anchor="center")
    tree.column("FrameRange", width=150, anchor="center", stretch=True)

    # 3) RenderNode column
    tree.heading("RenderNode", text="Render Node", anchor="center")
    tree.column("RenderNode", width=120, anchor="center", stretch=True)

    # 4) GSV column
    tree.heading("GSV", text="GSV", anchor="center")
    tree.column("GSV", width=180, anchor="center", stretch=True)
    
    tree.heading("Flags", text="Flags", anchor="center")
    tree.column("Flags", width=150, anchor="center", stretch=True)
    
    tree.heading("BatFile", text=".bat File", anchor="center")
    tree.column("BatFile", width=150, anchor="center", stretch=True)
    
    tree.heading("Status", text="Status", anchor="center")
    tree.column("Status", width=150, anchor="center", stretch=True)
    
     # Hidden column for full path
    tree.column("KatanaFullPath", width=0, stretch=False)
    tree.column("BatFullPath", width=0, stretch=False)
    tree.column("Switch", width=0, stretch=False)


    # No heading needed for "FullPath" if you don't want it visible:
    # tree.heading("FullPath", text="Full Path")  # optional
    
     # 1) Configure tags for special text colors
    #    'rendering' and 'rendered' both have gray text
    
    tree.tag_configure("rendering", foreground="#888888")  # or another shade of gray
    tree.tag_configure("rendered", foreground="#888888")
    tree.tag_configure("stopped", foreground="#888888")

    
    


    # Expand in all directions
    tree.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    return tree


# Queue management functions
def add_to_queue():
    katana_file = entry_katana_file.get()
    frame_range = entry_frame_range.get()
    render_node = entry_render_node.get()
    bat_file = entry_load_bat.get()             # full path for the .bat file
    flags_text = flags.get().strip()
    
    if not katana_file or not frame_range:
        log_debug("Please provide Katana File and Frame Range.\n")
        return
    
    
    # Display only the file name (last part) for both Katana and .bat file
    katana_display = os.path.basename(katana_file)
    bat_display = os.path.basename(bat_file) if bat_file else "Default"
    
    # Gather GSV entries into one string
    gsv_list = []
    for gsv_name_entry, gsv_value_entry, _ in gsv_entries:
        name = gsv_name_entry.get().strip()
        value = gsv_value_entry.get().strip()
        if name and value:
            gsv_list.append(f"{name}={value}")
    gsv_str = ", ".join(gsv_list)
    
    # The switch value from your CTkSwitch (assumed to return 1 for on, 0 for off)
    switch_value = switch.get()
    
    job_index = len(queue_tree.get_children()) + 1
    queue_tree.insert(
        "",
        "end",
        text=str(job_index),
        values=(katana_display, frame_range, render_node, gsv_str, flags_text, bat_display, "Queued",  katana_file, bat_file, switch_value )   
    )

    
    render_queue.put({
        "katana_file": katana_file,
        "frame_range": frame_range,
        "render_node": render_node,
        "gsv_entries": gsv_list,
        "flags": flags_text,
        "bat_file": bat_file,
        "switch": switch_value
    })
    queue_item_states.append(True)  # Add the job's state (True = enabled)
    # Log that this item has been added.
    log_debug(f"{katana_display} has been added to the queue.\n")
    

def remove_from_queue():
    selected_item = queue_tree.selection()
    if not selected_item:
        log_debug("Please select a render from the queue to remove.\n")
        return
    for item in selected_item:
        # Retrieve the Katana filename from this row
        item_values = queue_tree.item(item, "values")
        # item_values = (KatanaFile, FrameRange, RenderNode, GSV, FullPath)
        katana_file = item_values[0] if item_values and len(item_values) > 0 else "Unknown"
        # The displayed filename in your first column

        log_debug(f"Removed from '{katana_file}' queue \n")

        # Now actually remove it from the Treeview
        queue_tree.delete(item)
    # Optionally update render_queue here if needed # Update the UI to reflect the changes
    # if not queue_listbox.curselection():  # Check if any item is selected
    #     result_label.insert(tk.END, "Please select an item from the queue to remove.\n")
    #     return
    # selected_index = queue_listbox.curselection()[0]
    # queue_items = list(render_queue.queue)
    # if 0 <= selected_index < len(queue_items):
    #     del queue_items[selected_index]
    #     render_queue.queue.clear()
    #     for item in queue_items:
    #         render_queue.put(item)
    #     update_queue_display()
def clear_queue():
    # Check if there are items in the Treeview
    if not queue_tree.get_children():
        log_debug("There is nothing to clear in the queue.\n")
        return
    
    for item in queue_tree.get_children():
        queue_tree.delete(item)
    while not render_queue.empty():
        render_queue.get()
    # Log that the queue has been cleared
    log_debug("Queue has been cleared.\n")

def log_debug(message):
    result_label.configure(state=tk.NORMAL)
    result_label.delete(1.0, tk.END)
    result_label.insert(tk.END, message)
    result_label.configure(state=tk.DISABLED)
    result_label.update_idletasks()  # force update if needed

def render(tree):
    global render_process, stop_render_event, pause_event, completed_frames,clear_queue_button,pause_button,current_render_item, manually_stopped
    
    manually_stopped = False

    while not stop_render_event.is_set():
        items_to_render = [item for item in tree.get_children() 
                           if not set(tree.item(item, "tags")).intersection({"rendered", "stopped"})]
        if not items_to_render:
            break  # No more items to render

        current_render_item = items_to_render[0]
        current_index = tree.index(current_render_item)
        # get item data
        # item_values = tree.item(item_to_render, "values")
        item_values = list(tree.item(current_render_item, "values"))
        item_values[6] = "Currently Rendering"
         # Update on main thread:
        local_item = current_render_item
        local_values = tuple(item_values)
        root.after(0, lambda: update_item(local_item, local_values, ("rendered",), log_missing=False))
         # item_values is something like: ("template.katana", "1-10", "myRenderNode", "varA=1,varB=2")
        katana_full = item_values[7]  # Full path
        frame_range = item_values[1]
        render_node = item_values[2]
        flags_text = item_values[4]
        switch_value = item_values[9]  # hidden column

        # Lock the current index for rendering
        tree.currently_rendering_index = current_index
        tree.locked_indices.add(current_index)

        # # Mark the item as "rendering"
        # tree.item(item_to_render, tags=('rendering',))

        # Extract job details from the treeview row; only katana_file and frame_range are stored
        # katana_file, frame_range = tree.item(item_to_render, 'values')[1:]
        frame_list = parse_frame_range(frame_range)

        # Build the render command using the old code’s logic
        command = f'"{katana_bin}" --batch --katana-file="{katana_full}" -t {frame_range}'
        if render_node.strip():
            command += f' --render-node={render_node.strip()}'
        if int(switch_value) == 1:
            command += " --reuse-render-process"
        if flags_text:
            command += f" {flags_text}"
        for gsv_name_entry, gsv_value_entry, _ in gsv_entries:
            name = gsv_name_entry.get().strip()
            value = gsv_value_entry.get().strip()
            if name and value:
                command += f' --var {name}={value}'

        # Start the render process
        try:
            render_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True
            )

            # Monitor the render process
            while True:
                if stop_render_event.is_set() or pause_event.is_set():
                    break

                output = render_process.stdout.readline()
                if output == '' and render_process.poll() is not None:
                    break  # Process has finished

                if output:
                    handle_stdout(output.strip())

            render_process.wait()

        except Exception as e:
            log_debug(f"Error during rendering: {e}\n")

        finally:
            # Update status: if the render was stopped manually, mark as "Stopped Rendering",
            # otherwise "Done Rendering".
            if manually_stopped:
                item_values[6] = "Stopped Rendering"
            else:
                item_values[6] = "Done Rendering"
            # Mark the item as "rendered"
            local_item = current_render_item  # captured item id
            local_values = tuple(item_values)   # ensure it has the correct number of values (10 in this case)
            root.after(0, lambda: update_item(local_item, local_values, ("rendered",), log_missing=False))



            tree.locked_indices.add(current_index)
            tree.currently_rendering_index = None
            current_render_item = None

            # if completed_frames >= parse_frame_range(frame_range):
            #     break

    render_button.configure(state=tk.NORMAL)
    stop_render_button.configure(state=tk.DISABLED)
    progressbar.set(0)
    progressbar.stop()
    # Only log "Rendering Done!" if the rendering finished normally.
    if not manually_stopped:
        log_debug("Rendering Done!\n")
    clear_queue_button.configure(state=tk.NORMAL)
    pause_button.configure(state=tk.DISABLED)
    
def update_item(item, values, tag, log_missing=False):
    if item in queue_tree.get_children():
        try:
            queue_tree.item(item, values=values, tags=tag)
        except Exception as e:
            log_debug(f"Error updating item: {e}\n")
    else:
        if log_missing:
            log_debug("Item no longer exists in the tree.\n")

 
# Render management functions
def start_rendering():
    global render_thread, render_process, stop_render_event, pause_event,clear_queue_button,pause_button, current_render_item
    # Find only items that are not yet rendered or stopped.
    valid_items = [item for item in queue_tree.get_children() 
                   if not set(queue_tree.item(item, "tags")).intersection({"rendered", "stopped"})]
    if not valid_items:
        log_debug("Please add a render to the queue.\n")
        return
    
    if not queue_tree.get_children():
        log_debug("Please add a render to the queue.\n")
        return
    
    if render_thread and render_thread.is_alive():
        log_debug( "A render is already in progress.\n")
        
        return

    stop_render_event.clear()
    pause_event.clear()
    render_button.configure(state=tk.DISABLED)
    stop_render_button.configure(state=tk.NORMAL)
    pause_button.configure(state=tk.NORMAL)
    clear_queue_button.configure(state=tk.DISABLED)
    
    log_debug("Starting rendering...\n")
    render_thread = threading.Thread(target=lambda: render(queue_tree))
    render_thread.start()
    
        
def process_render(job):
    global current_render, stop_event, pause_event

    katana_file = job["katana_file"]
    frame_range = job["frame_range"]
    render_node = job["render_node"]
    flags = job["flags"]
    gsv_entries = job["gsv_entries"]

    command = f'"{katana_bin}" --batch --katana-file="{katana_file}" -t {frame_range}'
    if render_node:
        command += f' --render-node={render_node}'
    if switch.get() == 1:  # If reuse render process is enabled
        command += " --reuse-render-process"
    if flags:
        command += f" {flags}"
    for name, value in gsv_entries:
        if name and value:
            command += f' --var {name}={value}'

    try:
        log_debug( f"Starting render: {katana_file}\n")
        

        render_process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        if render_process:
            threading.Thread(target=monitor_render_output, args=(render_process,)).start()

    except Exception as e:
        log_debug( f"Error during render: {e}\n")
        

    finally:
        # After finishing the render, clear the current render
        current_render = None

        # Update the queue display to reflect the completed render
        # update_queue_display()

        # Move to the next job if the queue is not empty and stop was not triggered
        if not render_queue.empty() and not stop_event.is_set():
            start_rendering()
            
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
    global error_detected
    global stop_render_event
    global frame_range_list
    global rendering_stopped, manually_stopped
    
    error_detected = False
    def read_output(pipe, output_func):
        for line in iter(pipe.readline, ''):
            output_func(line)
    try:
        for line in iter(process.stdout.readline, ''):
            if stop_event.is_set():  # Check if stop event is triggered
                break

            if pause_event.is_set():  # Check if pause event is triggered
                continue

            handle_stdout(line)
            handle_stderr(line)
            check_frame_status(line)

        process.stdout.close()
        process.stderr.close()

    except Exception as e:
        result_label.configure(state=tk.NORMAL)
        result_label.insert(tk.END, f"Error reading output: {e}\n")
        result_label.configure(state=tk.DISABLED)

    finally:
        stop_event.set()  # Signal that rendering has stopped
        
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
    progressbar.configure(mode="determinate")  # Ensure it's determinate when complete
    
    if manually_stopped:
        result_label.delete(1.0, tk.END)
        result_label.insert(tk.END, "Rendering Stopped")
        progressbar.stop()
        rendering_stopped = True 
    elif error_detected:  # If an error was detected
            result_label.delete(1.0, tk.END)
            result_label.insert(tk.END, "Error Detected")
            progressbar.set(0)  # Set the progress to 100% (finished)
            progressbar.stop()
    else:  # Render finished successfully
            result_label.delete(1.0, tk.END)
            result_label.insert(tk.END, "Rendering Completed")
            progressbar.set(1)  # Set the progress to 100% (finished)
            progressbar.stop()
    
    manually_stopped = False

    # result_label.configure(state=tk.DISABLED)
            
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
    output_text.insert(tk.END, line+ "\n")
    output_text.yview(tk.END)
    update_progress(line, progressbar)
    check_frame_status(line)
    global error_detected  # We will track if an error occurred
    # You can add logic here to search for specific error keywords in the stdout output
    if check_error_in_line(line):
        error_detected = True
        log_debug("Error Detected\n")
    else:
        # Call a function to update progress bar if no error
        update_progress(line, progressbar)
    
def handle_stderr(line):
    output_text.insert(tk.END, line)
    output_text.yview(tk.END)
    global error_detected  # We will track if an error occurred
    # You can add logic here to handle errors from stderr as well
    if check_error_in_line(line):   
        error_detected = True
        log_debug("Error Detected\n")
        
    else:
        return
    
def check_error_in_line(line):
    lower_line = line.lower()
    if "[ERROR python.MainBatch]:" in lower_line or "attributeerror" in lower_line or "[error python.main]:" in lower_line or "Exiting with error code: -1" in lower_line or "(Error node: " in lower_line :
        return True
    return False   
             
def check_frame_status(output_line):
    # Check if a frame started rendering
    global initial_frame_rendering_detected
    global rendering_stopped
    
    # if rendering_stopped:
    #     return  # Stop checking the frames if rendering was stopped
    
    # For reuse rendering, check if "Frame: X" pattern is in the output
    if switch.get() == 1:
        # Look for the actual frame rendering line "Frame: X" (where X is the frame number)
        frame_match = re.search(r"Frame: (\d+)", output_line) or re.search(r"Rendering frame (\d+)", output_line)
        
        if frame_match:
            # Set the flag to True once we detect actual rendering frames
            initial_frame_rendering_detected = True
            
            # Get the frame number from the match
            current_frame = int(frame_match.group(1))
            # print(f"Rendering detected for frame: {current_frame}")
            
            # Update the label to show the current frame being rendered
            update_result_label(current_frame, is_completed=False)
            return

        # If we haven't seen "Frame: X", skip other processing
        if not initial_frame_rendering_detected:
            # print("Waiting for initial frame rendering to start...")
            return
    else:
        frame_match = re.search(r"Frame: (\d+)", output_line)
        
        if frame_match:
            # Set the flag to True once we detect actual rendering frames
            current_frame = int(frame_match.group(1))  # Assign current frame
            # Update the label to show the current frame being rendered
            update_result_label(current_frame, is_completed=False)
            return


    # Check for frame completion for both normal and reuse modes
    complete_match = re.search(r"Frame (\d+) completed", output_line)
    if complete_match:
        frame = int(complete_match.group(1))
        completed_frames.add(frame)
        
        update_result_label(frame, is_completed=True)
        
def update_result_label(frame, is_completed):
    """Update the label to show either the currently rendering frame or completed frame."""
    # Enable the result label (CTkTextbox) for updating
    result_label.configure(state=tk.NORMAL)
    katana_file = entry_katana_file.get()
    # Clear any previous text
    result_label.delete(1.0, tk.END)
    katana_file_name = os.path.basename(katana_file)
    
    # Display message based on rendering status
    if is_completed:
        result_label.configure(state=tk.NORMAL)
        result_label.delete(1.0, tk.END)
        completed_frames_str = ", ".join(map(str, sorted(completed_frames)))
        result_label.insert(tk.END, f"Frame {completed_frames_str} completed for {katana_file_name}")
    else:
        result_label.configure(state=tk.NORMAL)
        result_label.delete(1.0, tk.END)
        result_label.insert(tk.END, f"Currently rendering frame  {frame} for {katana_file_name}")
    
    # Disable the result label to make it read-only
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
    
    # Arnold
    # Search for the percentage in the output line
    if "done -" in output_line and "%" in output_line:
        try:
            
            # Extract the percentage value
            percentage = int(output_line.split("%")[0].split()[-1])
            # Convert the percentage to a value between 0 and 1
            progress = percentage / 100.0
            # Update the progress bar
            progressbar.configure(mode="determinate")
            progressbar.stop()
            progressbar.set(progress)
            # print(f"Updated progress to {progress}")
        except ValueError:
            pass  # Handle the case where the conversion to int fail
        
    # 3Delight
    # 2) Check for lines like "[INFO python.RenderLog]:    25%"
    elif "[INFO python.RenderLog]:" in output_line and "%" in output_line:
        try:
            # Example line: "[INFO python.RenderLog]:    25%"
            # Split on ']:', then strip, then remove '%'
            parts = output_line.split("]:")
            if len(parts) >= 2:
                # e.g. parts[1] = "    25%"
                percentage_str = parts[1].strip()
                # Remove trailing '%'
                if percentage_str.endswith("%"):
                    percentage_str = percentage_str[:-1].strip()
                # Convert to int
                percentage = int(percentage_str)
                progress = percentage / 100.0
                # Update the progress bar
                progressbar.configure(mode="determinate")
                progressbar.stop()
                progressbar.set(progress)
        except ValueError:
            pass
        
    #Redshift
    # elif "Block" in output_line and "rendered by GPU" in output_line:
    elif "Block" in output_line:
        # try:
            
            # Extract the percentage value
            block_info = output_line.split("Block ")[1].split(" ")[0]
            current_block, total_blocks = map(int, block_info.split('/'))
            # Convert the percentage to a value between 0 and 1
            percentage = (current_block / total_blocks) * 100
            progress = percentage / 100.0
            # Update the progress bar
            progressbar.configure(mode="determinate")
            progressbar.stop()
            progressbar.set(progress)
            # print(f"Updated progress to {progress}")
        # except ValueError:
        #     pass  # Handle the case where the conversion to int fail
    
    # After completing a frame or when rendering starts, set progress to indeterminate
    else:
        # If rendering is still in progress (e.g., processing next frame)
        progressbar.configure(mode="indeterminate")  # Set to indeterminate mode
        progressbar.start() 

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
    global render_process, stop_render_event, rendering_stopped, manually_stopped,clear_queue_button, pause_button, current_render_item

    manually_stopped = True
    
    if current_render_item is not None:
        item_values = list(queue_tree.item(current_render_item, "values"))
        katana_name = item_values[0] if item_values and len(item_values) > 0 else "Unknown"
        log_debug(f"The render '{katana_name}' was stopped.\n")
        # Update the status to "Stopped Rendering"
        item_values[6] = "Stopped Rendering"
        local_item = current_render_item  # capture current item id
        local_values = tuple(item_values)   # captured values
        root.after(0, lambda: update_item(local_item, local_values, ("stopped",), log_missing=False))

        # queue_tree.item(current_render_item, values=tuple(item_values), tags=("stopped",))
    else:
        log_debug("No active render to stop.\n")

    if render_process and psutil.pid_exists(render_process.pid):
        try:
            parent = psutil.Process(render_process.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            parent.wait()
            # log_debug("Batch rendering stopped.\n")
        except Exception as e:
            log_debug(f"Error stopping render: {e}\n")
    else:
        log_debug("No active render process to terminate.\n")

    # Reset state and re-enable/disble appropriate buttons.
    current_render_item = None
    render_button.configure(state=tk.NORMAL)
    stop_render_button.configure(state=tk.DISABLED)
    pause_button.configure(state=tk.DISABLED)  # Disable Pause/Resume once stopped.
    stop_render_event.set()
    rendering_stopped = True
    progressbar.configure(mode="determinate")
    progressbar.set(0)
    progressbar.stop()
    clear_queue_button.configure(state=tk.NORMAL)
        
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
    if file_path:
        entry_katana_file.delete(0, tk.END)
        entry_katana_file.insert(0, file_path)

def save_preset():
    katana_file = entry_katana_file.get()
    frame_range = entry_frame_range.get()
    render_node = entry_render_node.get()
    additional_flags = flags.get().strip()
    
    default_bat = ("katanabin", "katanabin.exe")

    if not katana_file or not frame_range:
        log_debug( "Cannot save preset without Katana File and Frame Range.")
        
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
            if katana_bin and katana_bin.lower() not in default_bat:
                file.write(f"Bat File: {katana_bin}\n")
            else:
                file.write("Bat File: \n")  
                
            reuse_flag_state = switch.get()
            file.write(f"Reuse Render Process: {reuse_flag_state}\n")
           
            if additional_flags:
                file.write(f"Additional Flags: {additional_flags}\n")


        #result_label.configure(text=f"Preset saved to {preset_name}")
        log_debug( f"Preset saved to {preset_name}")
          # Disable the CTkTextbox

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
            reuse_flag_state = None
            additional_flags = None
            render_node_value = None
            
            for line in file:
                if line.startswith("Katana File:"):
                    entry_katana_file.delete(0, tk.END)
                    entry_katana_file.insert(0, ":".join(line.split(":")[1:]).strip())
                elif line.startswith("Frame Range:"):
                    entry_frame_range.delete(0, tk.END)
                    entry_frame_range.insert(0, line.split(":")[1].strip())
                elif line.startswith("Render Node:"):
                    render_node_value = ":".join(line.split(":")[1:]).strip()  # Save render node value
                    entry_render_node.delete(0, tk.END)
                    entry_render_node.insert(0, line.split(":")[1].strip())
                elif line.startswith("GSV:"):
                    parts_gsv = line.split(":")[1].strip().split("=")
                    if len(parts_gsv) == 2:
                        add_gsv_entry(parts_gsv[0], parts_gsv[1])
                elif line.startswith("Bat File:"):  # Check for .bat file in the preset
                    loaded_katana_bin = ":".join(line.split(":")[1:]).strip()
                elif line.startswith("Reuse Render Process:"):
                    # Load the saved switch state
                    reuse_flag_state = int(line.split(":")[1].strip())
                elif line.startswith("Additional Flags:"):
                    additional_flags = ":".join(line.split(":")[1:]).strip()
                    flags.delete(0, tk.END)
                    flags.insert(0, additional_flags)


            if loaded_katana_bin:
                katana_bin = loaded_katana_bin
                bat_file_name = os.path.basename(loaded_katana_bin)
                entry_load_bat.delete(0, tk.END)
                entry_load_bat.insert(0, katana_bin)
                load_bat_file()
                log_debug( f".bat file loaded from preset: {bat_file_name}")  # Add new text
                
            else:
                katana_bin = "katanaBin.exe"
                entry_load_bat.delete(0, tk.END)  # Clear the .bat file path
                log_debug( "Using default KatanaBin.exe")  # Add new text
                
            
            if reuse_flag_state is not None:
                switch.select() if reuse_flag_state == 1 else switch.deselect()
            else:
                switch.select() if reuse_flag_state == 0 else switch.deselect()
            
            if additional_flags is not None:
                flags.delete(0, tk.END)
                flags.insert(0, additional_flags)
            else:
                flags.delete(0, tk.END)
            
            # Handle Render Node: Clear if not in the preset
            if render_node_value is not None:
                entry_render_node.delete(0, tk.END)
                entry_render_node.insert(0, render_node_value)
            else:
                # Clear the field if no value was found in the preset
                entry_render_node.delete(0, tk.END)
                # entry_render_node.insert(0, "No render node provided.")  # Optional: default text
                

def add_gsv_entry(name=None, value=None):
    global gsv_entries  # Ensure we're modifying the global variable

     # Create or use an existing scrollable frame
    gsv_name_entry = customtkinter.CTkEntry(gsv_frame, height=30, width=100,fg_color=forgro_color,border_color=forgro_color, placeholder_text="Var")
    gsv_name_entry.grid(row=len(gsv_entries) + 1, column=0, padx=10, pady=(5, 5), sticky="nsew")

    gsv_value_entry = customtkinter.CTkEntry(gsv_frame, height=20, width=100,fg_color=forgro_color,border_color=forgro_color, placeholder_text="Value")
    gsv_value_entry.grid(row=len(gsv_entries) + 1, column=1, padx=10, pady=(5, 5), sticky="nsew")

    remove_button = customtkinter.CTkButton(gsv_frame, text="Remove", width=100, height=24, command=lambda: remove_gsv_entry(gsv_name_entry, gsv_value_entry, remove_button))
    remove_button.grid(row=len(gsv_entries) + 1, column=2, padx=5, pady=(5, 5), sticky="nsew")

    gsv_entries.append((gsv_name_entry, gsv_value_entry, remove_button))
    
    # Set the values if provided
    if name is not None and value is not None:
        gsv_name_entry.insert(0, name)
        gsv_value_entry.insert(0, value)


def remove_gsv_entry(gsv_name_entry, gsv_value_entry, remove_button):
    global gsv_entries  # Ensure we're modifying the global variable

    # Remove the GSV entry and destroy associated widgets
    gsv_entries.remove((gsv_name_entry, gsv_value_entry, remove_button))
    gsv_name_entry.destroy()
    gsv_value_entry.destroy()
    remove_button.destroy()
    
def suspend_process_tree(proc):
    """Recursively suspend a process and all its children."""
    for child in proc.children(recursive=True):
        try:
            child.suspend()
        except Exception as e:
            print(f"Could not suspend child {child.pid}: {e}")
    proc.suspend()
    
def resume_process_tree(proc):
    """Recursively resume a process and all its children."""
    for child in proc.children(recursive=True):
        try:
            child.resume()
        except Exception as e:
            print(f"Could not resume child {child.pid}: {e}")
    proc.resume()
    
def pause_render():
    global render_process
    result_label.configure(state=tk.NORMAL)
    if not pause_event.is_set():
        pause_event.set()
        try:
            if render_process and psutil.pid_exists(render_process.pid):
                proc = psutil.Process(render_process.pid)
                suspend_process_tree(proc)  # <-- recursively suspend
                log_debug("Process tree suspended successfully.\n")
            else:
                log_debug("No render process found to suspend.\n")
        except Exception as e:
            log_debug(f"Error pausing process: {e}\n")
        progressbar.stop()
        progressbar.configure(mode="determinate")
        log_debug( "Pausing render...\n")
    else:
        try:
            if render_process and psutil.pid_exists(render_process.pid):
                proc = psutil.Process(render_process.pid)
                resume_process_tree(proc)  # <-- recursively resume
                log_debug("Process tree resumed successfully.\n")
            else:
                log_debug("No render process found to resume.\n")
        except Exception as e:
            log_debug(f"Error resuming process: {e}\n")
        pause_event.clear()
        progressbar.configure(mode="indeterminate")
        progressbar.start()
        log_debug( "Resuming render...\n")
    result_label.configure(state=tk.DISABLED)



def load_bat_file():
    global katana_bin
    bat_file_path = entry_load_bat.get()

    if bat_file_path:
        katana_bin = bat_file_path
        bat_file_name = os.path.basename(bat_file_path)
        # result_label.configure(text=f"KatanaBin.exe loaded from: {katana_bin}")
        log_debug( f"KatanaBin.exe loaded from: {bat_file_name}")  # Add new text
          # Disable modifications
    else:
        katana_bin = "katanaBin.exe"
        # result_label.configure(text=f"Using default KatanaBin.exe")
        log_debug( "Using default KatanaBin.exe")  # Add new text
          # Disable modifications

def change_appearance_mode_event(new_appearance_mode: str):
    global forgro_color
    customtkinter.set_appearance_mode(new_appearance_mode)
    if new_appearance_mode == "Light":
            forgro_color="white"
            entry_katana_file.configure(fg_color=forgro_color,border_color=forgro_color)
            entry_frame_range.configure(fg_color=forgro_color,border_color=forgro_color)
            entry_render_node.configure(fg_color=forgro_color,border_color=forgro_color)
            entry_load_bat.configure(fg_color=forgro_color,border_color=forgro_color)
            tabview.configure(fg_color=forgro_color,border_color=forgro_color, segmented_button_fg_color="gray", segmented_button_unselected_color="gray", segmented_button_unselected_hover_color="gray")
            gsv_frame.configure(fg_color=forgro_color)
            flags.configure(fg_color=forgro_color,border_color=forgro_color)
            forgro_color="gray"
            for gsv_name_entry, gsv_value_entry, _ in gsv_entries:
                gsv_name_entry.configure(fg_color=forgro_color,border_color=forgro_color)
                gsv_value_entry.configure(fg_color=forgro_color,border_color=forgro_color)
            
            

    elif new_appearance_mode == "Dark" :
        # Dark mode styling
            forgro_color="#1d1e1e"
            entry_katana_file.configure(fg_color=forgro_color,border_color=forgro_color)
            entry_frame_range.configure(fg_color=forgro_color,border_color=forgro_color)
            entry_render_node.configure(fg_color=forgro_color,border_color=forgro_color)
            entry_load_bat.configure(fg_color=forgro_color,border_color=forgro_color)
            tabview.configure(fg_color="#212121",border_color=forgro_color, segmented_button_fg_color=forgro_color, segmented_button_unselected_color=forgro_color, segmented_button_unselected_hover_color="#292a2a")
            gsv_frame.configure(fg_color="#212121")
            flags.configure(fg_color=forgro_color,border_color=forgro_color)
            for gsv_name_entry, gsv_value_entry, _ in gsv_entries:
                gsv_name_entry.configure(fg_color=forgro_color,border_color=forgro_color)
                gsv_value_entry.configure(fg_color=forgro_color,border_color=forgro_color)
            
    else:  # Assume "System" defaults to dark for this example
        forgro_color= None
        entry_katana_file.configure(fg_color=entry_katana_file.cget("fg_color"))
        return
    
        
def browse_bat_file():
    global katana_bin
    """Function to browse for the .bat file, clear the entry, and load it."""
    # Clear the entry field
    
    # katana_bin = "katanaBin.exe"
    # result_label.configure(state=tk.NORMAL)  # Allow modifications
    # result_label.delete("1.0", tk.END)  # Clear existing text
    # result_label.insert(tk.END, "Using default KatanaBin.exe")  # Add new text
    # result_label.configure(state=tk.DISABLED)  # Disable modifications
    
    # Open file dialog to select .bat file
    file_path = filedialog.askopenfilename(filetypes=[("Batch Files", "*.bat")])
    
    # If a file was selected, insert its path in the entry and load the file
    if file_path:
        entry_load_bat.delete(0, tk.END)
        entry_load_bat.insert(0, file_path)
        load_bat_file()
        
    else:
            katana_bin = "katanaBin.exe"
            log_debug("Using default KatanaBin.exe")  # Add new text
            



if __name__ == '__main__':
    # Initialize CustomTkinter
    customtkinter.set_ctk_parent_class(tkinterDnD.Tk)
    customtkinter.set_appearance_mode("Dark")
    customtkinter.set_default_color_theme("blue")

    # Create main window
    root = customtkinter.CTk()
    root.geometry("900x630")
    root.title("Katana Batch Renderer")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=100)
    # Set custom icon
    icon_path = "WindowsIcon.ico"  # Replace with the path to your .ico file
    root.iconbitmap(icon_path)
    root.resizable(True, True)

    # GUI setup

    # -------------------------------------------------------------------
    # Sidebar
    sidebar_frame = customtkinter.CTkFrame(master=root, width=140, corner_radius=0)
    sidebar_frame.grid(row=0, column=0, rowspan=10, sticky="NWSE")
    sidebar_frame.grid_rowconfigure(0, weight=1)
    sidebar_frame.grid_columnconfigure(1, weight=1)
    # Save Preset button
    save_preset_button = customtkinter.CTkButton(master=sidebar_frame,width=5, text="Save Preset", command=save_preset)
    #save_preset_button = tk.Button(root, text="Save Preset", command=save_preset)
    save_preset_button.grid(row=3, column=0, pady=(20,5), padx=(10, 10),sticky="N")

    # Load Preset button
    load_preset_button = customtkinter.CTkButton(master=sidebar_frame, width=5, text="Load Preset", command=load_preset)
    #load_preset_button = tk.Button(root, text="Load Preset", command=load_preset)
    load_preset_button.grid(row=4, column=0, pady=(5,10), padx=(10, 10), sticky="N")


    my_image = customtkinter.CTkImage(light_image=Image.open("WindowsIcon.ico"),
                                    dark_image=Image.open("WindowsIcon.ico"),
                                    size=(60, 60))

    image_label = customtkinter.CTkLabel(sidebar_frame, image=my_image, text="",)  # display image with a CTkLabel
    image_label.grid(row=0, column=0, pady= 30,padx= 10, sticky="NWE")
    Name_label = customtkinter.CTkLabel(sidebar_frame, text="KBR", font=('Arial-bold', 40))
    Name_label.grid(row=0, column=0,pady= 100,padx= 10, sticky="NWE")  
    #apperance window

    # appearance_mode_label = customtkinter.CTkLabel(master=sidebar_frame, text="Appearance Mode:", anchor="w")
    # appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
    # appearance_mode_optionemenu = customtkinter.CTkOptionMenu(master=sidebar_frame, values=["Light","Dark"],
    #                                                                         command=change_appearance_mode_event)
    # # appearance_mode_optionemenu = customtkinter.CTkOptionMenu(master=sidebar_frame, values=["Light", "Dark","System"],
    # #                                                                         command=change_appearance_mode_event)
    # appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))
    # # Set the default value (for example, "Light")
    # appearance_mode_optionemenu.set("Dark")
    
    frametest = customtkinter.CTkFrame(master=sidebar_frame,height=10, fg_color="transparent" )
    frametest.grid(row=5, column=0, )


    # ---------------------------------------------------------------------------------------------------
    # Main content
    # Mainbar_frame = customtkinter.CTkFrame(root)
    # Mainbar_frame.grid(row=1, column=1, sticky="NWSE")

    main_frame = customtkinter.CTkTabview(master=root , segmented_button_fg_color="#1d1e1e", segmented_button_unselected_color="#1d1e1e", segmented_button_unselected_hover_color="#292a2a",fg_color="#212121")
    main_frame.grid(row=0, column=1, padx=20, pady=5, sticky="NWSE")
    main_frame.add("Add Render")
    main_frame.add("Render Queue") 
    main_frame.add("Render Log") 

    # -------------------------------------------------------
    # create Footer frame with widgets
    footer_frame = customtkinter.CTkFrame(master=root, corner_radius=0, height=30, fg_color="transparent" )
    footer_frame.grid(row=12, column=0,  columnspan=2,  sticky="WSE")
    footer_frame.grid_rowconfigure(0, weight=50)
    footer_frame.grid_rowconfigure(1, weight=1)
    footer_frame.grid_columnconfigure(0, weight=1)
    footer_frame.grid_columnconfigure(1, weight=1)
    footer_frame.grid_columnconfigure(2, weight=2)
    # emptyResult label
    emptyresult_label = customtkinter.CTkLabel(footer_frame, text="Output:   ", font=('Arial', 11))
    emptyresult_label.grid(row=0, column=1, pady=1, sticky="E")  

    # Result label
    result_label = customtkinter.CTkTextbox(footer_frame, wrap=tk.WORD, height=3, width=10, font=('Arial', 11))
    result_label.grid(row=0, column=2, padx=20,  pady=5, sticky="nsew")
    # Footer label
    footer_label = customtkinter.CTkLabel(footer_frame, height=10,  text= "This Script was written by Oluwajomiloju Osho with the help of ChatGPT", font=('Arial', 8),)

    footer_label.grid(row=0, column=0, padx=10, pady=10,sticky="W")
    # ------------------------------------------------------



    main_frame.tab("Add Render").grid_columnconfigure(0, weight=1)
    main_frame.tab("Add Render").grid_columnconfigure(1, weight=1)
    main_frame.tab("Add Render").grid_columnconfigure(2, weight=10)
    main_frame.tab("Add Render").grid_columnconfigure(3, weight=1)


    main_frame.tab("Add Render").grid_rowconfigure(5, weight=1)

    # main_frame.tab("Add Render").grid_rowconfigure(6, weight=1)

    main_frame.tab("Render Log").grid_columnconfigure(0, weight=1)
    main_frame.tab("Render Log").grid_rowconfigure(0, weight=1)
    # Configure grid for the Render Queue tab
    main_frame.tab("Render Queue").grid_columnconfigure(0, weight=1)
    
    main_frame.tab("Render Queue").grid_rowconfigure(0, weight=1)
    # Add a Listbox to display the queue
    # queue_listbox = CTkListbox(
    #     main_frame.tab("Render Queue"),
    #     command=lambda selected: show_value(selected),
    #     height=200,
    #     width=400,
    #     corner_radius=8,
    #     border_color=forgro_color,
    #     fg_color=forgro_color,
    #     text_color="white",
    #     hover=True,
    #     highlight_color="light blue"
    # )
    # queue_listbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
    queue_tree = create_treeview(main_frame.tab("Render Queue"))
    # Add Move Up and Move Down buttons
    queue_button_frame = customtkinter.CTkFrame(main_frame.tab("Render Queue"), fg_color="transparent")
    queue_button_frame.grid(row=3, column=0, pady=10, sticky="ew")
    queue_button_frame.grid_columnconfigure(0, weight=1)
    queue_button_frame.grid_columnconfigure(1, weight=1)
    queue_button_frame.grid_columnconfigure(2, weight=1)
    queue_button_frame.grid_columnconfigure(3, weight=1)

    # move_up_button = customtkinter.CTkButton(
    #     queue_button_frame,
    #     text="Move Up",
    #     command=lambda: move_item_in_queue(-1)  # Move item up
    # )
    # move_up_button.grid(row=0, column=0, padx=5 )

    # move_down_button = customtkinter.CTkButton(
    #     queue_button_frame,
    #     text="Move Down",
    #     command=lambda: move_item_in_queue(1)  # Move item down
    # )
    # move_down_button.grid(row=0, column=1, padx=5)
    # # Add buttons for queue management
    # queue_button_frame = customtkinter.CTkFrame(main_frame.tab("Render Queue"))
    # queue_button_frame.grid(row=2, column=0, pady=10)


    remove_queue_button = customtkinter.CTkButton(
        queue_button_frame,
        text="Remove from Queue",
        command=lambda: remove_from_queue()
    )
    remove_queue_button.grid(row=0, column=2, padx=5, )

    clear_queue_button = customtkinter.CTkButton(queue_button_frame, text="Clear Queue",command=clear_queue)
    clear_queue_button.grid(row=0, column=3, padx=5)

    # Update the queue display initially
    # update_queue_display()
    # -----------------------------------------------------
    # # Output log



    # Queue display
    queue_frame = customtkinter.CTkFrame(main_frame.tab("Add Render"), fg_color="transparent")
    queue_frame.grid(row=10, column=0, columnspan= 4, padx=20, pady=5, sticky="NWSE")
    queue_frame.grid_columnconfigure(0, weight=1)
    queue_frame.grid_columnconfigure(1, weight=1)
    queue_frame.grid_columnconfigure(2, weight=10)
    queue_frame.grid_columnconfigure(3, weight=1)
    # # Buttons for queue management
    # queue_button_frame = customtkinter.CTkFrame(queue_frame, fg_color='blue')
    # queue_button_frame.grid(row=0, column=2,columnspan= 4, pady=10)
    add_button = customtkinter.CTkButton(queue_frame, text="Add to Queue", command=add_to_queue)
    add_button.grid(row=0, column=4, padx=5,sticky="E")
    switch = customtkinter.CTkSwitch(queue_frame, text=f"Reuse Render Process")
    switch.grid(row=0, column=0, padx=(5, 10),  pady=10,sticky="W")
    # remove_button = customtkinter.CTkButton(queue_button_frame, text="Remove from Queue", command=lambda: remove_from_queue(queue_listbox.curselection()[0]))
    # remove_button.grid(row=0, column=1, padx=5)
    # clear_button = customtkinter.CTkButton(queue_button_frame, text="Clear Queue", command=clear_queue)
    # clear_button.grid(row=0, column=2, padx=5)

    output_frame = customtkinter.CTkFrame(main_frame,fg_color="#212121")
    output_frame.grid(row=5, column=0,columnspan=3, pady=10, sticky="NWSE")
    output_frame.grid_columnconfigure(0, weight=1)
    output_frame.grid_columnconfigure(1, weight=1)
    output_frame.grid_columnconfigure(2, weight=1)

    # render_button = customtkinter.CTkButton(output_frame, text="Start Rendering", command=start_rendering)
    # render_button.grid(row=0, column=0, padx=20, pady=5, sticky="NWSE")
    render_button = customtkinter.CTkButton(output_frame, text="Start Rendering", command=start_rendering)
    render_button.grid(row=0, column=0, padx=20, pady=5, sticky="NWSE")
    stop_render_button = customtkinter.CTkButton(output_frame, text="Stop Render", command=stop_render, state=tk.DISABLED)
    stop_render_button.grid(row=0, column=1, padx=20, pady=5, sticky="NWSE")
    pause_button = customtkinter.CTkButton(output_frame, text="Pause/Resume", command=pause_render, state=tk.DISABLED)
    pause_button.grid(row=0, column=2, padx=20, pady=5, sticky="NWSE")

    # # Progress bar
    progressbar = customtkinter.CTkProgressBar(output_frame, orientation="horizontal")
    progressbar.grid(row=1, column=0, columnspan=3, padx=20, pady=10, sticky="NWSE")
    progressbar.set(0)
    # ------------------------------------------------------------------
    # Output text widget
    output_text = customtkinter.CTkTextbox(main_frame.tab("Render Log"), wrap=tk.WORD, height=400, width=400, corner_radius=8)
    output_text.grid(row=0, column=0,  sticky="nsew")
    output_text.configure(state=tk.NORMAL)  # Allow modifications
    root.protocol("WM_DELETE_WINDOW", cleanup_on_close)
    # ---------------------------------------------------------------------------


    label_katana_file = customtkinter.CTkLabel(main_frame.tab("Add Render"), anchor="w", text="Katana File:")
    label_katana_file.grid(row=1, column=0, padx=(20, 0), pady=5, sticky="W")
    entry_katana_file = customtkinter.CTkEntry(master=main_frame.tab("Add Render"),fg_color=forgro_color,border_color="#1d1e1e", placeholder_text="Browse to the Directory of your .Katana file")
    entry_katana_file.grid(row=1, column=1, columnspan=2, padx=(20, 0), pady=(5, 5), sticky="nsew")
    #btn_browse_katana_file = tk.Button(root, text="Browse", command=browse_katana_file,)
    btn_browse_katana_file = customtkinter.CTkButton(master=main_frame.tab("Add Render"), text="Browse", command=browse_katana_file)
    btn_browse_katana_file.grid(row=1, column=3, padx=10, pady=5, sticky="W")

    # Frame Range input
    label_frame_range = customtkinter.CTkLabel(master=main_frame.tab("Add Render"), anchor="w", text="Frame Range:")
    label_frame_range.grid(row=2, column=0, padx=(20, 0), pady=5, sticky="nsew")
    entry_frame_range = customtkinter.CTkEntry(master=main_frame.tab("Add Render"),fg_color="#1d1e1e",border_color="#1d1e1e", placeholder_text="1-3,5-10")
    entry_frame_range.grid(row=2, column=1, columnspan=2, padx=(20, 0), pady=(5, 5), sticky="nsew")


    # Render Node input
    label_render_node = customtkinter.CTkLabel(master=main_frame.tab("Add Render"), justify=customtkinter.LEFT, text="Render Node (optional):")
    label_render_node.grid(row=3, column=0, padx=(20, 0), pady=(5, 10), sticky="W")

    entry_render_node = customtkinter.CTkEntry(master=main_frame.tab("Add Render"),fg_color="#1d1e1e",border_color="#1d1e1e", placeholder_text="Enter the node to render from")
    entry_render_node.grid(row=3, column=1, columnspan=2, padx=(20, 0), pady=(5, 10), sticky="nsew")



    # Load .bat file input
    label_load_bat = customtkinter.CTkLabel(master=main_frame.tab("Add Render"), anchor="w", text=".bat File:(Optional)")
    label_load_bat.grid(row=0, column=0,   padx=(20, 0),pady=(10, 0), sticky="W")
    entry_load_bat = customtkinter.CTkEntry(master=main_frame.tab("Add Render"), fg_color="#1d1e1e",border_color="#1d1e1e", placeholder_text="Select Batch launcher")
    entry_load_bat.grid(row=0, column=1, columnspan=2,  padx=(20, 0), pady=(10, 5), sticky="nsew")
    btn_browse_bat = customtkinter.CTkButton(master=main_frame.tab("Add Render"), text="Browse", command=browse_bat_file )
    #btn_browse_bat = tk.Button(root, text="Browse", command=lambda: entry_load_bat.insert(tk.END, filedialog.askopenfilename(filetypes=[("Batch Files", "*.bat")])))
    btn_browse_bat.grid(row=0, column=3, pady=(10, 0), padx=(10, 5),sticky="WN")

    # # Load .bat file button
    # load_bat_button = customtkinter.CTkButton(master=Mainbar_frame, text="Load .bat File", command=load_bat_file)
    # #load_bat_button = tk.Button(root, text="Load .bat File", command=load_bat_file)
    # load_bat_button.grid(row=0, column=4, pady=(50, 0), padx=(5, 50),sticky="WN")

    # Run the application
    tabview = customtkinter.CTkTabview(master=main_frame.tab("Add Render"), segmented_button_fg_color="#1d1e1e", segmented_button_unselected_color="#1d1e1e", segmented_button_unselected_hover_color="#292a2a",fg_color="#212121", height=100, width=100)
    tabview.grid(row=5, column=0, columnspan=4,  pady=5,padx=(20,20), sticky="nsew")
    tabview.add("GSV")
    tabview.add("Flags")
    tabview.tab("GSV").grid_columnconfigure(0, weight=1)
    tabview.tab("GSV").grid_rowconfigure(0, weight=1)
    tabview.tab("GSV").grid_rowconfigure(1, weight=1)
    # configure grid of individual tabs
    tabview.tab("Flags").grid_columnconfigure(0, weight=1)
    tabview.tab("Flags").grid_rowconfigure(1, weight=1)

    flags = customtkinter.CTkEntry(tabview.tab("Flags"), height=200,bg_color="transparent", fg_color="#1d1e1e",border_color="#1d1e1e", placeholder_text="Enter additional rendering flags")
    flags.grid(row=0, column=0,rowspan=4, sticky="nsew")


    # Initialize the GSV frame outside the add_gsv_entry function
    gsv_frame = customtkinter.CTkScrollableFrame(tabview.tab("GSV"), width=1,fg_color=forgro_color, corner_radius=0, orientation='vertical')
    gsv_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
    gsv_frame.grid_columnconfigure(0, weight=3)
    gsv_frame.grid_columnconfigure(1, weight=3)
    gsv_frame.grid_columnconfigure(2, weight=1)
    gsv_frame.grid_rowconfigure(0, weight=0)  # Adjust the weight
    gsv_frame.grid_rowconfigure(1, weight=0)  # Adjust the weight
    gsv_frame.grid_rowconfigure(2, weight=0)  # Adjust the weight

    # Add GSV button
    add_gsv_button = customtkinter.CTkButton(tabview.tab("GSV"), text="Add GSV Entry", command=add_gsv_entry)
    #add_gsv_button = tk.Button(root, text="Add GSV Entry", command=add_gsv_entry)
    add_gsv_button.grid(row=0, column=2, pady=10, padx=(5, 10), sticky="N")
    root.mainloop()
