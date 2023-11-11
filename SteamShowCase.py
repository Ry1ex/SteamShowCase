from tkinter import Tk, Label, Button, filedialog, ttk, PhotoImage, messagebox, IntVar, Checkbutton , Text, Scrollbar, END , Toplevel , LEFT, RIGHT
from moviepy.editor import VideoFileClip
from PIL import Image, ImageSequence, ImageOps
from io import BytesIO
import io
import threading
import os
import numpy as np
import shutil
import traceback
import sys

#Thank chatGPT/Copilot/GoogleTrad for the traduction and comment

# This is a little trick to hide the output of the program and for --noconsole with pyinstaller work
# C'est un petit truc pour masquer la sortie du programme et pour que --noconsole avec pyinstaller fonctionne
stream = io.StringIO()
sys.stdout = stream
sys.stderr = stream

# Custom message box with themed appearance
# Boîte de message personnalisée avec apparence thématique
def custom_messagebox(title, message, master=None):
    messagebox = Toplevel(master)
    messagebox.title(title)
    messagebox.configure(bg="#333333")
    messagebox.resizable(False, False)
    messagebox.iconphoto(False, PhotoImage(file="SteamShowCaseLogo.png"))
    message_label = Label(messagebox, text=message, bg="#333333", fg="#ffffff", font=("Arial", 12))
    message_label.pack(padx=20, pady=20)
    ok_button = Button(messagebox, text="OK", command=messagebox.destroy, bg="#333333", fg="#ffffff", borderwidth=1, relief="solid", width=15)
    ok_button.pack(pady=10)

    messagebox.update_idletasks()
    width = messagebox.winfo_width()
    height = messagebox.winfo_height()
    x = (messagebox.winfo_screenwidth() // 2) - (width // 2)
    y = (messagebox.winfo_screenheight() // 2) - (height // 2)
    messagebox.geometry(f'+{x}+{y}')

    return messagebox

# Modifies the end-of-file character for a GIF to ensure proper looping
# Modifie le caractère de fin de fichier d'un GIF pour assurer une boucle correcte
def modify_gif_hex(gif_path):
    with open(gif_path, 'rb') as file:
        content = file.read()
    content = content[:-1] + b'\x21' if content.endswith(b'\x3B') else content
    with open(gif_path, 'wb') as file:
        file.write(content)

# Restores the end-of-file character to its original state for a GIF file
# Restaure le caractère de fin de fichier à son état original pour un fichier GIF
def restore_gif_hex(gif_path):
    with open(gif_path, 'rb') as file:
        content = file.read()
    if not content.endswith(b'\x3B'):
        content += b'\x3B'
    with open(gif_path, 'wb') as file:
        file.write(content)

# Resizes a GIF to a new height, maintaining aspect ratio
# Redimensionne un GIF à une nouvelle hauteur, en conservant le rapport d'aspect
def resize_gif(gif_path, base_height=720):
    with Image.open(gif_path) as gif:
        width, height = gif.size
        new_height = base_height
        new_width = int(new_height * width / height)
        resized_gif = gif.resize((new_width, new_height), Image.Resampling.LANCZOS)
        resized_gif.save(gif_path)

# Calculates the number of frames and frame delay to optimize GIF size
# Calcule le nombre de cadres et le délai entre eux pour optimiser la taille du GIF
def calculate_optimization_parameters(frames, target_fps, segment_duration, max_size_mb, fps_min ):
    original_frame_count = len(frames)
    current_fps = min(target_fps, original_frame_count / segment_duration)
    frames_to_keep = round((original_frame_count / target_fps) * current_fps)
    frame_size_estimates = []

    for frame in frames:
        with BytesIO() as buffer:
            frame.save(buffer, format="GIF")
            frame_size_estimates.append(len(buffer.getvalue()))
    average_frame_size = sum(frame_size_estimates) / len(frame_size_estimates)

    while current_fps > fps_min:
        estimated_size = frames_to_keep * average_frame_size
        if estimated_size <= max_size_mb * 1024 * 1024:
            break
        current_fps -= 1
        frames_to_keep = round((original_frame_count / target_fps) * current_fps)

    if current_fps < fps_min:
        current_fps = fps_min

    return frames_to_keep, int(1000 / current_fps)

# Adjusts frame duration for the given number of frames to keep
# Ajuste la durée des cadres pour le nombre donné de cadres à conserver
def adjust_frame_duration(frames_to_keep, total_duration):
    if frames_to_keep > 0:
        return total_duration / frames_to_keep
    else:
        return total_duration

# Optimizes GIF by selecting a subset of frames and adjusting frame duration
# Optimise un GIF en sélectionnant un sous-ensemble de cadres et en ajustant la durée des cadres    
def optimize_gif(gif_path, frames_to_keep, frame_duration):
    with Image.open(gif_path) as gif:
        frames = [frame.copy() for frame in ImageSequence.Iterator(gif)]
        original_frame_count = len(frames)
        selected_indices = np.linspace(0, original_frame_count - 1, frames_to_keep).astype(int)
        new_frames = [frames[i] for i in selected_indices]
        new_frames[0].save(gif_path, save_all=True, append_images=new_frames[1:], optimize=True, loop=0, duration=frame_duration)
        modify_gif_hex(gif_path)

# Reduces the color palette of the GIF to decrease file size
# Réduit la palette de couleurs du GIF pour diminuer la taille du fichier
def reduce_gif_quality(gif_path, num_colors=128, dither=False):
    with Image.open(gif_path) as gif:
        frames = [frame.copy() for frame in ImageSequence.Iterator(gif)]
        frames_quantized = [frame.quantize(colors=num_colors, method=Image.MEDIANCUT, dither=dither) for frame in frames]
        frames_quantized[0].save(gif_path, save_all=True, append_images=frames_quantized[1:], optimize=True, loop=0)

# Validates if the input character is a digit
# Valide si le caractère entré est un chiffre
def only_numbers(char):
    return char.isdigit()

# Main application class for the Steam Showcase video to GIF converter
# Classe principale pour l'application de conversion de vidéo en GIF pour Steam Showcase
class SteamShowcaseApp:

    # Initializes the application, GUI elements, and variables
    # Initialise l'application, les éléments de l'interface utilisateur et les variables    
    def __init__(self, root):
        self.root = root
        root.title('SteamShowCase')
        root.resizable(False, False)
        self.fps_min_var = IntVar(value=10)
        self.reduce_quality_var = IntVar(value=0)

        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 8) - (width // 8)
        y = (root.winfo_screenheight() // 8) - (height // 8)
        root.geometry(f'+{x}+{y}')


        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", background="#333333", foreground="#ffffff", borderwidth=1, relief="solid")
        style.configure("TProgressbar", troughcolor="#333333", bordercolor="#000000", lightcolor="#333333", darkcolor="#000000", barcolor="#26C4F4")
        style.configure("Custom.Horizontal.TProgressbar", background="#26C4F4" , borderwidth=1,thickness=20)
        style.configure("TCheckbutton", background="#333333", foreground="#ffffff")
        style.configure("TLabel", background="#333333", foreground="#ffffff")
        style.configure("TEntry", background="#333333", foreground="#ffffff", fieldbackground="#555555")
        style.configure("TFrame", background="#333333")
        style.configure("TLabelFrame", background="#333333")
        style.configure("TPanedwindow", background="#333333")

        style.map("TButton",
          foreground=[('active', '#ffffff')],
          background=[('active', '#1E1E1E')],
          bordercolor=[('active', '#ffffff'), ('!active', '#000000')])
        
        style.map("TCheckbutton",
          foreground=[('active', '#ffffff')],
          background=[('active', '#1E1E1E')],
          bordercolor=[('active', '#ffffff'), ('!active', '#000000')])
        
        button_frame = ttk.Frame(root)
        button_frame.grid(row=2, column=0, columnspan=3)
        button_frame.grid_propagate(False) 
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.configure(background="#333333")

        self.root.iconphoto(False, PhotoImage(file="SteamShowCaseLogo.png"))
        self.label = Label(root, text="SteamShowcase", font=("Arial", 28), bg="#333333", fg="#ffffff")
        self.label.grid(row=0, column=0, columnspan=3, pady=20)

        self.logo = PhotoImage(file="SteamShowCaseLogo.png").subsample(5, 5)
        self.logo_label = Label(root, image=self.logo, bg="#333333")
        self.logo_label.grid(row=1, column=0, columnspan=3)
        
        self.select_video_button = ttk.Button(root, text="Select Video", command=self.select_video, width=15)
        self.select_video_button.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.select_output_folder_button = ttk.Button(root, text="Select Output Folder", command=self.select_output_folder, width=20)
        self.select_output_folder_button.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        self.start_button = ttk.Button(root, text="Start", command=self.start_conversion , width=15)
        self.start_button.grid(row=2, column=2, padx=10, pady=10, sticky="ew")

        self.slow_down_gif_var = IntVar(value=1)
        self.slow_down_gif_checkbox = ttk.Checkbutton(root, text="Slow down GIFs to match the visuals of the video", variable=self.slow_down_gif_var)
        self.slow_down_gif_checkbox.grid(row=3, column=0, columnspan=3, pady=10)

        self.reduce_quality_checkbox = ttk.Checkbutton(root, text="Reduce quality of gif if the gif are more than 5MB", variable=self.reduce_quality_var)
        self.reduce_quality_checkbox.grid(row=4, column=0, columnspan=3, pady=10)

        self.fps_min_label = Label(root, text="Desired FPS", bg="#333333", fg="#ffffff")
        self.fps_min_label.grid(row=5, column=0, pady=10, sticky="e")

        vcmd = (self.root.register(only_numbers), '%S')
        self.fps_min_entry = ttk.Entry(root, textvariable=self.fps_min_var, validate='key', validatecommand=vcmd , width=3)
        self.fps_min_entry.grid(row=5, column=1, pady=10, padx=(10, 0), sticky="w")
        
        self.progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate" , style="Custom.Horizontal.TProgressbar")
        self.progress.grid(row=6, column=0, columnspan=3, pady=20)
        
        self.instruction_label = Label(root, text="Instructions for uploading GIFs to Steam", wraplength=300, cursor="hand2", bg="#333333", fg="#ffffff")
        self.instruction_label.grid(row=7, column=0, columnspan=4, pady=20)
        self.instruction_label.bind("<Button-1>", self.show_instructions)
        
        self.language_button = ttk.Button(root, text="Mode French", command=self.toggle_language)
        self.language_button.grid(row=8, column=2, pady=10)
        
        self.language = "english"
        
        self.video_selected = False
        self.output_folder_selected = False
        
        self.texts = {
            "english": {
                "window_title": "SteamShowcase",
                "select_video": "Select Video",
                "select_output_folder": "Select Output Folder",
                "start": "Start",
                "slow_down_gif": "Slow down GIFs to match the visuals of the video",
                "reduce_quality": "Reduce quality of gif if the gif are more than 5MB",
                "fps_min": "Desired FPS",
                "instructions": "Instructions for uploading GIFs to Steam",
                "language_toggle": "Mode French",
                "upload_instructions": """
Step 1:
Open your browser and go to this link: https://steamcommunity.com/sharedfiles/edititem/767/3/#

Name the gif and upload the gif.

Step 2:
Before clicking on "Save and continue"
Open "Inspect Element", click on "Console" then enter:
$J('[name=consumer_app_id]').val(480);$J('[name=file_type]').val(0);$J('[name=visibility]').val(0);

Step 3:
Click on "Save and continue".

Step 4:
On your profile, add a Workshop Showcase and select your gifs.
                """
            },
            "french": {
                "window_title": "SteamShowcase",
                "select_video": "Sélectionner la vidéo",
                "select_output_folder": "Sélectionner le dossier de sortie",
                "start": "Démarrer",
                "reduce_quality": "Réduire la qualité du gif si les gifs dépasse 5MB",
                "fps_min": "FPS désiré",
                "slow_down_gif": "Ralentir les GIF pour qu'il corresponde au visuel de la video",
                "instructions": "Instructions pour télécharger des GIFs sur Steam",
                "language_toggle": "Mode English",
                "upload_instructions": """
Étape 1:
Ouvrez votre navigateur et rendez-vous sur ce lien : https://steamcommunity.com/sharedfiles/edititem/767/3/#

Nommez le gif et téléchargez le gif.

Étape 2:
Avant de cliquer sur "Enregistrer et continuer"
Ouvrez "Inspecter l'élément", cliquez sur "Console" puis entrez :
$J('[name=consumer_app_id]').val(480);$J('[name=file_type]').val(0);$J('[name=visibility]').val(0);

Étape 3:
Cliquez sur "Enregistrer et continuer".

Étape 4:
Sur votre profil, ajoutez une vitrine Workshop Showcase et sélectionnez vos gifs.
                """
            }
        }
        
        self.update_language(self.language)
    
    # Opens a file dialog to select a video file
    # Ouvre une boîte de dialogue pour sélectionner un fichier vidéo
    def select_video(self):
        file_path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
        if file_path:
            self.video_path = file_path
            self.video_selected = True
            self.update_selection_status()
    
    # Opens a file dialog to select an output directory
    # Ouvre une boîte de dialogue pour sélectionner un répertoire de sortie
    def select_output_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.output_folder_path = folder_path
            self.output_folder_selected = True
            self.update_selection_status()
    
    # Starts the conversion process in a separate thread
    # Démarre le processus de conversion dans un thread séparé
    def start_conversion(self):
        if self.video_selected and self.output_folder_selected:
            self.progress['value'] = 0
            self.progress['maximum'] = 100
            threading.Thread(target=self.conversion_thread, daemon=True).start()
        else:
            custom_messagebox("Selection Required", "Please select a video and an output folder.", master=self.root)

    # Reduces GIF quality by resizing frames (I think is not my best idea)
    # Réduit la qualité du GIF en redimensionnant les cadres (Je pense que ce n'est pas ma meilleure idée)
    def reduce_gif_quality2(self, gif_path, resize_factor=2):
        try:
            with Image.open(gif_path) as img:
                frames = []
                print(f"Traitement du GIF : {gif_path}")
                for i, frame in enumerate(ImageSequence.Iterator(img)):
                    print(f"Traitement du cadre {i}")
                    frame = frame.convert('RGBA')
                    resized = frame.resize((frame.width // resize_factor, frame.height // resize_factor), Image.NEAREST)
                    resized = resized.resize((resized.width * resize_factor, resized.height * resize_factor), Image.NEAREST)
                    frames.append(resized)

                frames[0].save(gif_path, save_all=True, append_images=frames[1:], optimize=False, loop=0)
                print("GIF sauvegardé avec succès.")
        except Exception as e:
            print(f"Erreur globale lors de la réduction de la qualité du GIF {gif_path}: {e}")
            traceback.print_exc()
            raise

    # Checks and optimizes segment sizes if they exceed a certain threshold
    # Vérifie et optimise la taille des segments s'ils dépassent un certain seuil
    def optimize_segment_sizes(self, segment_paths, max_size_mb=5, default_resize_factor=2):
        need_optimization = False
        for segment_path in segment_paths:
            if os.path.getsize(segment_path) > max_size_mb * 1024 * 1024:
                need_optimization = True
                break

        if need_optimization:
            self.master.after(100, lambda: messagebox.showinfo("Information", "The segments exceed 5 MB the program will reduce the quality"))
            for i, segment_path in enumerate(segment_paths):
                try:
                    if os.path.exists(segment_path):
                        self.reduce_gif_quality2(segment_path, default_resize_factor)
                    else:
                        print(f"Le segment {i+1} n'existe pas: {segment_path}")
                except Exception as e:
                    print(f"Erreur lors de l'optimisation du segment {segment_path}: {e}")
                    traceback.print_exc()

    # The method that runs on a separate thread to perform conversion
    # La méthode qui s'exécute sur un thread séparé pour effectuer la conversion
    def conversion_thread(self):
        try:
            self.update_progress(10)
            video_clip = VideoFileClip(self.video_path)
            if video_clip.duration > 10:
                video_clip = video_clip.subclip(0, 10)
            gif_path = os.path.join(self.output_folder_path, "preview.gif")

            video_clip.write_gif(gif_path, fps=30, program='ffmpeg')
            self.update_progress(30)
            fps_min_user = self.fps_min_var.get()
            
            with Image.open(gif_path) as gif:
                width, height = gif.size
                frames = [frame.copy() for frame in ImageSequence.Iterator(gif)]
                segment_duration = min(10, video_clip.duration)
                frames_to_keep, frame_delay = calculate_optimization_parameters(frames, 30, segment_duration, 5, fps_min=fps_min_user)
                
                should_slow_down = self.slow_down_gif_var.get() == 1
                if should_slow_down:
                    frame_duration = adjust_frame_duration(frames_to_keep, segment_duration * 1000)
                else:
                    frame_duration = frame_delay
                
                segment_paths = []

                for i  in range(5):
                    left = i * width // 5
                    right = (i + 1) * width // 5 if i < 4 else width
                    segment_frames = [frame.crop((left, 0, right, height)) for frame in frames]
                    segment_path = os.path.join(self.output_folder_path, f"segment_{i+1}.gif")
                    segment_frames[0].save(segment_path, save_all=True, append_images=segment_frames[1:], loop=0, duration=frame_duration)
                    segment_paths.append(segment_path)
            
            self.update_progress(50)
            for segment_path in segment_paths:
                reduce_gif_quality(segment_path)
                optimize_gif(segment_path, frames_to_keep, frame_duration)
                #modify_gif_hex(segment_path)  # Out of index wtf ???
                default_resize_factor = 2  
                restore_gif_hex(segment_path)
                if self.reduce_quality_var.get() == 1:
                    default_resize_factor = 2  
                    self.reduce_gif_quality2(segment_path, default_resize_factor)
                modify_gif_hex(segment_path) 

            self.update_progress(80)
            modify_gif_hex(segment_path) 
            self.update_progress(100)
            custom_messagebox("Success", "The GIFs have been successfully created and optimized.", master=root)
        except Exception as e:
            messagebox.showerror("Error", {e})
            traceback.print_exc()
        finally:
            self.update_progress(0)

    # Updates the progress bar in the GUI
    # Met à jour la barre de progression dans l'interface utilisateur
    def update_progress(self, value):
        self.progress['value'] = value
        self.root.update_idletasks()
    
    # Updates the status of video and output folder selection
    # Met à jour le statut de la sélection de la vidéo et du dossier de sortie
    def update_selection_status(self):
        if self.video_selected:
            self.select_video_button.config(text=self.texts[self.language]["select_video"] + " ✔")
        else:
            self.select_video_button.config(text=self.texts[self.language]["select_video"])
        if self.output_folder_selected:
            self.select_output_folder_button.config(text=self.texts[self.language]["select_output_folder"] + " ✔")
        else:
            self.select_output_folder_button.config(text=self.texts[self.language]["select_output_folder"])
    
    # Toggles the application language between English and French
    # Bascule la langue de l'application entre l'anglais et le français
    def toggle_language(self):
        self.language = "french" if self.language == "english" else "english"
        self.update_language(self.language)
    
    # Updates all text elements in the GUI according to the selected language
    # Met à jour tous les éléments textuels de l'interface utilisateur en fonction de la langue sélectionnée
    def update_language(self, language):
        texts = self.texts[language]
        self.root.title(texts["window_title"])
        self.select_video_button.config(text=texts["select_video"])
        self.select_output_folder_button.config(text=texts["select_output_folder"])
        self.start_button.config(text=texts["start"])
        self.instruction_label.config(text=texts["instructions"])
        self.language_button.config(text=texts["language_toggle"])
        self.slow_down_gif_checkbox.config(text=texts["slow_down_gif"])
        self.reduce_quality_checkbox.config(text=texts["reduce_quality"])
        self.fps_min_label.config(text=texts["fps_min"])
    
    # Displays a window with instructions for uploading GIFs to Steam
    # Affiche une fenêtre avec des instructions pour télécharger des GIFs sur Steam
    def show_instructions(self, event):
        instructions = self.texts[self.language]["upload_instructions"]
        instruction_window = Toplevel(self.root)
        instruction_window.title("Instructions")
        instruction_window.resizable(False, False)

        icon_image = PhotoImage(file="SteamShowCaseLogo.png")
        instruction_window.iconphoto(False, icon_image)

        text_widget = Text(instruction_window, wrap='word', height=18, width=115, background="#333333", foreground="#ffffff")
        text_widget.pack(expand=True, fill='both')
        text_widget.insert('end', instructions)
        text_widget.config(state='disabled')
        
        close_button = ttk.Button(instruction_window, text="Close", command=instruction_window.destroy , bg="#333333", fg="#ffffff")
        close_button.pack()

# Entry point for the application; creates the main window and launches the app
# Point d'entrée de l'application ; crée la fenêtre principale et lance l'application
if __name__ == "__main__":
    root = Tk()
    app = SteamShowcaseApp(root)
    root.mainloop()















# Yes it's Gaben i juste want to make a joke because i love easteregg 

#                                                 ^JG#&&###BGGBBGGPGBBBB######BGGPYJJJ?7~~!!!!!!!!~~~!~^^^^^^^~!!~~^^^^^^^~~~!!!~~~~~~~~~!!7!!!!!!!!77?J??JJJ???JJYY555PPPGGBBGGBBGGPP5PPPGGGGGGP5J?!!~:                                                                                                      
#                                                .7P######BBBBBBBGGGPGGGBB#BBBBGP5YJ???!~~!7!!!~!!~~~~~^^^^^^~~!~~^^^^::^^~~~~~~~~~~~!~^^~!7!!!!!!!!!!7????JJJ?JJJJYYYY55PPPPGGBBBBBGGPPPPPGGGGGGP5J7~~^.                                                                                                     
#                                               .!PB###BBBBGGBBBGPPPPPGGPGBGGPGG5YYJJ?7!!!777!~~~~~~~^^^^^^^^~~~~~~^:::^^^^~~~~~~~~~~~~^^^~!!!~~~!!~~~!7777?JJJ?JYYYYYYY5PGP5PGBBBBBBBGGGGGGGGGGGGP5J7~^:                                                                                                     
#                                              .~5B###BBBBGGGGGGP55PPGGGGGGGPPP5YJYYJ??777777!~~~~~^^^^^^^^^^~~~~~~^::^^^^^~~~~~~~~~~~~~^^^^~!!~~~!~~~~!777?JJJ??JYYYYYY55PPPPPGBB####BBBGGGGGGGGGGPY?7~^.                                                                                                    
#                                             .~YG####BBGGPPGGP555PGGGGGGGBGGP55YJYYYJ??7777!~~~~~~~^^^^^^^^~~^^^^^^^^^^^^^^~~~~^^~~~!!~^^^^^~!!!~~!!~~!77??JJJJJJJYY555555PGGGGB####&##BBBBGGGGBBBGPYJ7!^.                                                                                                   
#                                             :JGBBBBBBBGGPPPP5Y5PGGGPPGGB#BGP555Y5YJJ??7777!~~!~^~~^^^^^^^^^^^^~^^^^^^^^^^^^~~~~^~~~!!~~~^^^^~~!!!!!!!~!!7??JYYYYYY5555PPPPPPGGB#####&###BBBGGGGBBBGPYJ7!~:                                                                                                  
#                                            .!5BBBB##BBGGGPPP55PBBGGGBB###BGPPGP5YYJJ??JJ?7!!!~~^^^^^^^^^^::^^^^^^^^^^:^^^^^~~~^^~~~~~~~~~~~~^^^~~!!777!77??JYY55555555PGGGPPPPPB######&####BGGBBBBBGPYJ?7~:                                                                                                 
#                                            :JG######BBBBBBGGGBBBBGBB###BBBBBGGP5YYYJJJJ?7!!7!~~^^^^^^^^^:::^^^^^^^^^::^^^^^~~^^^^~~~~~^~~~~~~^^^^^~!77?JJYYY5555PP555PPPPGGBGGGPPGB#&&##&&###BBBBGBBG5YJ?7~.                                                                                                
#                                           .7PB#&&&&######&&&###BB######B##BBGP5YYYYJJJ?7!777!~~~~^^^^^^:::^^^^^^^^:::::^^^^~~^^^^^^~~^^^^^^^~~~~~^~~~~!!7?JYYY55555555PGGPGGBBBBBGGGGB#####&&&###BB#BG5J??7^.                                                                                               
#                                          .~YB#&&&&&&&&&&&&&&&##########&##BGP5YJJYYJJ??77777!!~~~^^^^^^::^^^^^^^::::::::::^^^^^^^:^^^^^^^^^^^^~~^~~~~~~~!!7?JYY55YY555PGBBGGGGBB##BBBBBB####&&&&##B##BPYJJ?!^.                                                                                              
#                                          :?G#&&&&&&&@@@@@@&&&&########&##BBGPYYY5YYJ?77??7777!~~~^^^^^^^^^~~^^^^::::::::::::^^^::::::::::^^^^^^:::^^^~~~~~!7?JJY555555PGBB##BGGGGGBB#########&&&&&###BGPYYJ?!:                                                                                              
#                                         .!5#&&&&&&@@@@@@@&&&##BB#########BGP55PP5J?7777777777!~~^^^^^~^^^^^^:^^^::::::::^::::^^^^:::::::::::::^^::::^^^^^^^~~!?JY5PPPPPGGBB#&&##BBBBBBBB##&&&&##&&&###BBP5YJ7~.                                                                                             
#                                         ^YB#&&&&&@@@@@&&&&&#############BGPPGPPY?7??7777!!7!!~~~~^^~^^^^^^^^^^^^^::::^^^^^^^^:^~^:::::::^^^:^^^:::::::^^^^^^^~~!7JYPGGGGGGBBB#&&############&&&&&&&#####BP5J?7^                                                                                             
#                                        :7P#&&&&@@@&&&&&###############BGGGGGPYJ??J??7777777!!!7777!~~~~~~~^^^^^^^^^^^^~~~^^^^:^~~^^^^^^^^^~~!~~~~~~~^^^^~~~~~~~~!7?JY5PGGBB#BBB##&######&&&&&&&&&&&&&&&#BGPYJ7~.                                                                                            
#                                        ^JB#&&&@@@&&&&&###############BGGGGG5J???JJ???JJJJ?JJJJJ???JJJJJ?77!!~~~^^^^^^~~!~~~^^^^!!!~~~~!~^~7J??JJYJJJJ??777777!!!777?JY5PPPGGBB#BB##&&&####&&####&&&&&&###BP5Y?!:                                                                                            
#                                       .7G#&&&&&&&&&#&##############BBBBBG5YYJJYYYJJYYY55YY55555555555PP555YJJ?7~^~~~~~~~~~~^^~!7?7777777!7YPP55555YJJJJJ???7777!77777??JY55PGGGB######&&&#######BB#######BGPY?!^.                                                                                           
#                                       ^YB#&&&&&&###############BBBBGGGPP5YYYY555PPPPPPP55555PPPPGGPPGGGGPP55YY?!!!!~!!!~~^^^^~!7????????7?YPGP5YYYYYYJJ???77!!!!7777777?JJY555PGGB#############BGPPGBBBBBBGPY?!~.                                                                                           
#                                      .7G#&&&&&&###&&&###BBBBBGGPP555555YYYYY555PPP55YYJJJJJJJJJJJY555555555YYJ?777!!!!!~~^::::^~!7???7???7?JYYJ???JJJJJ??77777!!!!!!777??JY555PPGGBB##########BBGGPPGGGGGGPP5J7~:                                                                                           
#                                     .^Y#&&&&&&&#&&&&##BGGGGGPPP5YYYYYYYYYJJYY55YJJ??7!^^^:^^^~~~!!!!77?????JJ??JJ??77!!~~^:....::^~!!!7!~~~!77!!777777!!!~~!!!!~~~!!77777?JYYYY5PPGB##########BBBBBBBBBBBGGPP5?~:                                                                                           
#                                     .~P&&&&&&&&&&@@&&#GPPPPPP55YJJJJYYYJJJJYYJJJ??7!~^^^^:.....:::^^~~!!7777??JYYYYJ?7!~^^:......::^~~^^~~!!~~~~~~~^^^^^^:::^^^^^^~!~^~!777?Y55YYY5PGBB######B###&###BBGGPGPP5J!^.                                                                                          
#                                     :?B&@@@&&&&&@@&&#####BBGPP55YYJJJJJJYYYYYYYJ?77!~!!!^^:^~~~~~~~^^:^^^~!7?JY5555YJ?!~^:.....:::::^~~!77~^::::.............::::..:~!~~~~!7?Y5555555PGGGGBBBBBBBBBGGGP55555PPY7^.                                                                                          
#                                    .~Y#&@@@&&&&&&@&#BPPGGGGGGBGGPPP55PPPPPPP5JJ???JJYYY?!!!777!77?JJ?7!~^^~!?Y555555YJ7~^^^::...:::.:!J?!^^^:::::::^~!~^^::........:^~7!~^~!!77JY555555PPGGGGGGP5555555555555P5J!^.                                                                                         
#                                   .:!5#&@&&&&###&&&&#GPPGP55YYY5555YPB#B555J?JJY5PPPPPGGGGB#B5Y5J77JYY55YJJYY5PGP5Y5PPPY?77!~~~~~^::~7!~!77!!777??JJY55J????7!~^^:::::~!!777??777JYY55PGBB####GP5YJJYYY555YYYYYY?!:                                                                                         
#                                   .^?G#&&&&#BBGB#&&&#BGPGPP5YYY5YJ?7?YPPGBGYJY5GBBBB##GPP5P##PJ7^:^755YJJY55555Y5PPGGG57^::...:~7?JJ?!^^!7?JY5PPY??5GB#BGGGPYJJ???7~^^^^^~^^~5#PJ?JY55PGBB####GPPGPYJJJJYY5YJJ???7~.                                                                                        
#                                   :!5B&&&&#BGP55G#&&&#GPPPP5YYY5YJ77777?Y555555PGGPPP5YY5YYPP5?7~^::^^^^^~!?JJJJ5PP555J7~^^:....:~Y5?^^~~^^~7J55J77JY5G#BPY?7?Y55PP5?~^^^7JJJ5GY!~~7?JJY5GGB#BGPPPGPYJJ?77?JJJJJ?7~:                                                                                        
#                                  .~YB&&&##BBGP5YPB#&&&BGGPP5YY55Y?7!!!77?JJJJYYYYJJ???????77!!~^^::....::^~!!!?5PP5555J7!~^:...:.:~??!^^^^^^~~!!!!7777?J?77~^^~!!!!777^^!7?!~~~~~~~~!77?YPGBBBGGGGGGPYJ??77?JJ????!:.                                                                                       
#                                  ^YB#&&###BGGP5Y5G#&&&BGPPP55Y5YY?7!!!!7????7777????77!~^^^^^^^^:::::::::^~~!7YPGPPP55J7~^:::.::.:~?JJ?!^:^~~~~~~~^~~~~~~~^:::.::...:^:^!7~:::::^^^^~~!7J5GBBBBBGBBBGP5YJ77??J????7~.                                                                                       
#                                 :?G########BGP555P#&&&#GPPP55Y5YJ??77!!77???7~~!!77!!~~^^^^^^^^^^^^:::::^~~!7J5PPPPP5Y?!~^:......:^7Y57^:^^^~^^^^^^^^^^^^^^:::.:::....:~~^::::::::^~~~~7J5PBB##BBB##BBGPY?????JJJ??!.                                                                                       
#                                .~YB########BGGP5PGB#&&#BPPP5555YJJJ?7!!!!!7!!!~~~~!~~~~~^^^^^^^^^^^:^^^^^~!?JYYY5555YJ7!^::.....::::^!!~~~~~~^^^^^::::^^^^^:::.......:!~:.......::^^~~!7J5PGB###BB###BGGP5JJ??JYYJ?~.                                                                                       
#                                ^JPB####BB###BBGPPGB#&&#BPP555YYYYJJJ?777777!!!!~~~~~~~~~^^^^^^^^^^^^^^~~~7JJJJJYYYYJJ7!~^::.....:::...:^^~~!!~^^^^^^^^^^^^:::......:~!^:........::^^~~!!?Y5G###BBB###BBBGP5YJJY55Y?~.                                                                                       
#                               .7YPB####BB#&&#BGPPGB#&&#BPP55YYYYYYJJJ???7777!!!!~~~~~~^^^^^^^^^:^^^^^~!?JJJJ?JJYJJJJ?7~^^::......:::....:~77!~~~^^^^^^^^^^::::...:~!~:...........::^~~~!?J5GB##BBB####BBGGGP5Y5PPPY!:                                                                                       
#                               ^?J5GB#####&&&##BGGB#&&&#BPP55YYYYYYYYJJJJ???7777!!~~~~~!!!77!!~~~~!!777??JJJJJJYYJJ??7!~^:::......:::::..:!JY?7!~~^^^^^^^^^:::^^~!~^:..............::~~~!7JYPB##BBB####BBGGBGGPPGGGPJ^.                                                                                      
#                               :7J5GBBB###&###&#BB#&&&&#GPP55Y55YYYYYJJJYJJ??7777!!!!~~~~~~!!~!!!~~~~^~!77?JYYYYYYJJ?7~^^::......::::::::^!JYYJ?7!!!77777??77!~^::..................:^~~~!7J5GB###BBBBBBBBGGBGPPGGGPY!.                                                                                      
#                               .!YPGBB##&####&&#B##&&&&#GPP55Y55YYYYYYYYYYJJ?77!!!~~~~^^^:::::::::::::^!7?JY55555YYJ?7~^^::.. ....:::::::^~777???777777777!^::.......................:^~~~!7?5B###BBBBBB##BBBBGPGGGP57:                                                                                      
#                                ^JPB##&&##B#&&&###&&&&#BGPPP555YYYYYYYYYYJJJ??7!~~~^:::::.........:::^!7?Y5PGGP5YYJ?7!~^^:..   ....::.....:~!!~~~~~~^^^^^::::...........:............:^^~^~~!?P#&#BBBBBBBBBBBBGGGBBG5?:                                                                                      
#                                .7PB#&&##B#&&##B#&&&&##GGPPP55YYYYYYYYYYYJJJ??7!~~^^::::::......:::^~7?Y5GGP5YYYJJ?7!~^^:...   ............:~!!~^^^^:::::::..............::...::.::::::^^^^~~75###BBBGGGGBBBBBBGGGBGPJ~.                                                                                     
#                                .!5####BB#&&&###&&&&&#BGGPPP55YYYYY55YYYYYYJJ?!!~~^^^:::::....:::^~7?Y5PP5YJ??7?JJ?7~^:::..    .............:!??7!~~^^^:::::::.........:::::::::::::::::^^^^^~JG##BBBGP5PGBB#BBGGGGGG5!.                                                                                     
#                                :?G###B##&&&###&&&&&#BGGPPPP55YYYY5555YYYYYJJ?7!~~^^^::::::.:::^~!?YPPPP5YJ?7777?JJ7~^::...    ............::~?5Y?!~~~~^^:::::::::....:::::::::::::::::::::^^^75B###BGP5PGBBBBGGGGGGGY~.                                                                                     
#                               :?G#####&&&&&##&&&&&#BGGGPPPP55YYYYYY55YYYYJJJ?7!~~^^^:::::::::^~7J5GGP5YYYYJYYYYJJJ?!^:..........::^~!!!!~~~~~!?YJJ?7!!~~^^::::::::::::::::::::::::::::::^^::^!YB&&#BGP5PGBBBBBGGGGGG5~.                                                                                     
#                              ^JG#####&&&&&&&&&&&#BBGGGPP55555YYYYYYYYYYYYJJJ?7!~~^^^^^::::::^~7J5PPYJ?JYY5PGBBGP55YJ7~^:::....::^!YB####G5?!^^^~7JYJ?7!~~^^^^::::::::::::::::::::::::::::::::~?G&&#BGPPPB##BBBBBBBGP5!.                                                                                     
#                             :JPBB##&&&&&&&&&&&&&#BBGGGPPP5555YYYYYYYYYYYYYYJ?77!~^^^^^^:::^^~7JYYJ?????JY55PPPGGPP5YJ?7!~^^:::^~7Y5PPPGPY7~::.::^~7?J?77!!~^^^^::::::::::::::::::::::::::::^^^!5B#BBGPPG######BBBBBBP7.                                                                                     
#                            .7PBBB#&&&&&&&&&&&&&&#BBGGPP555555YYYYYYYYYYYYYYJ?77!~~^^^:::::^~!???7777???JJJYY55PPP55555YJ?77777?7!~~~~~~^^:.......:^~!7???7!~~^^^^^^^::::::::::::::::::::::::^^~?5PGGGPGB#######BBBBBP?.                                                                                     
#                            ^YGBB#&&&&&&&&&&&&&&&#BGGPP555555YYYYYYYYYYYYYYYJ?7!!!~^^^^::^^^~!777!!77??JJJJJJYYYYYYY55555YYY55Y?!~^::::::::::......:::^~!7777!!~^^^^^^:::::::::::::::::::::::^^^!JPBBBGB&&#######BBBGP7.                                                                                     
#                           :7PGBB#&&&&&&&&&&&&&&&#BGPPP5555555YYYYYYYYYYYYYJJ?7!~~~^^:::^^^^~~!!!77???JYYYYYYYYYYJJJJJ??77!777!~^^^:::::::::::......:::::^^^~~!!~~~~^^^:::::::::::::::::::::::^^~75GGB#&&&##BBBB###BBP?.                                                                                     
#                           ^JPGBB&&&&&&&&&&&&&&&&BGGGPPP555555YYJJJJJYYYYYJJ??7!~~^^^::::^^^~~!!777??JJYYYYYJJJJ???7!~~^^::::^^^^^::::::::::::::...:::::::::::^^^^^^^^^:::::::::::..::::::::::::^~7JP#&@@&##BGPPGGB#BGJ:                                                                                     
#                          .~YGBB#&&&&&&&&&#&&&&&&BPPPPPPPPP555YYYYYYYJJJJJJ??7!!~~^^^::::^^~~~!!!77???JJYYJJ??77!!~~^::::::::::^^::::::..::::::::::::::..::::::::::::::::::::::::...:::::::::::^^~~7P#&&&&&&##BBGPGGGGY^                                                                                     
#                          .!5GB#&&&&&&&&&##&&@&&&&#BGPPPPPPP555YYYYYYJJJJJJ?77!~~~^^^^^:^^^~~~~!!!!77???JJ??7!~~^^^^::::::..................::::::::::::.::::::::::::::::::::::.....::::::::::::~~!75#@@&&&&###BGPPGGGY^                                                                                     
#                          .75B#####&&&&&###&&@&&#&&&&#BPPPPP5555YYYYYJJJJJJ?77!~~~~^^^^^^^^^~~~~~~~!!7777!!!~~~~~~~~!!!!~~^^^^^~~!!!!~~~~^:::::::::::..:::::::::::::::::::::::......:::::::::::^~~!JG&@@&&&###BBGPPGGPY^                                                                                     
#                          .!5B##B##&&&&&###&&&&##&&@@&#GPPPPPP555YYYYJJJ???77!!~~~~^^^^^~^^^^^^^^^^~!77!!~!!77?J55PPGGBBBBGGGGGGGGGPPPPGGPP5YJ?7!^^::^^::::::::::::::::::::::......::::::::::::^~7YG&@&&&&#####BBBBBGGY^                                                                                     
#                          .~YGGGG#&&&&&&#B#&&&&##&&&@&#GPPPPPPP555YYYJJ???777!!~~~~^~~~~~^^^^^^::^~!77??JY5GBB##BBGPP5YJJ???77!!!!!!77?JJY5PPPP55Y??77!!~^^^::::::::::::::::.........::::::::::^7G&@@&&&&&######BBBBBB5^                                                                                     
#                          .~J5PB#&&&&&&&BBB&&&#BB#&&&&&BGGPPPP5555YYYYJJ???77!!~~~~~~~~~~^^^^^:::^~7J5PG##&##BPY7~^:::........::...:::::::::^^^~~^^^^^^^^::::::::::::::::::....:.....:::::::::.^J#@@&&&&&&#####BBBBBBBP!.                                                                                    
#                          .^?PB#&###&&&#BBB#&&&####&&&&BGGGPPP5555YYYJJJ???77!!~~~~~~~~^^^^:::::^~7YPPPPP5YYJ??77!~~~^^^^^^^^^^^^^::::::::::::::::...::::::::::::::::::::::.......::::::::::::.^5&@@&&&&&##BB##BBBBBBBG7.                                                                                    
#                           ^?G#&####&&&#BBB#&&&#####&&&#BGGPPPP5555YYYJJJ???777!!~~~~~^^^:::::::^~7??????7777777777!~~~~~~~~~~~!!!~~~^^^:::::::::...::...::::::::::::::::::.......:::::::::::::!P&&&&&&&&#BGB##BBBBBB#BJ:                                                                                    
#                           ^YB&&#BB#&&&#BGB#&&&###B#&&&#BBGGPPP55555YYJJJJ???777!~~~~~^^^:::::::^~!!!!7???????77??77!!!!!!77777??77!~~^^::............::::::::::::::::::::.........:::::::::::^?B&&##&&&##GGGBBBBB####BY:                                                                                    
#                           ~P#&&#GG#&&&#BGB#&&&####B#&&&BBGGPPPP5555YYYJJJ??7777!!~~~~^^::::::::::^^~~!!!!7777777777!!!!!!777!!!!!!~~^:::.................:::...:::::::..:.......:::::::::::::~Y#&&&#&&&#BGPGBBBB######P~                                                                                    
#                          .7B&&&BPPB&&&#BGGB&&&&##BB#&&&#BGGGPPP5555YYYJJ???77?77!~~~~^^^::::::::::^^~~~~~!!!!!!!!!!~!!!~~~!!!~~~^^^::::.......................:::::::.::::....::::::::::::::^7P&@&&&&&&#GPPGB#B#######G!.                                                                                   
#                          .JB&&&B5PB&&&#BGGB&&&&&#BBB&&&#BGGGPPP55555YYYJJ??????7!!!~~^^^^:::::::::^^~~~~~~~~~~^^^^^^^^^^^~~^^^:^^^::::.......................::..::::::::::...::::::::::::::^?G&@&&&&&&#GPPGB####&####BJ:                                                                                   
#                          .JB#&&B55B&&&&#BPG#&&&&&BGB#&&&#BGPP55555555YYYJJJ????7777!~~^^^^^^^^^^::^^^^^^^^^^^^:::::::::::^^^::::::::::.......................:....::::::::::.:::::::::::::^^~?B&@&&&&&&#GPPG####&&####BP!.                                                                                  
#                          .?G#&#GY5G#&&&&BGG#&&&&&#BB#&&&&BGPPP55555555YYYYJJ?????77!!~~~~^^^^^^^^^^^^^^^^^^:::::::::::::::::::::::::::.........................:::::::::::::..::::::::::::^^~J#&@&&&&&#BBGPG#####&&####BY^                                                                                  
#                          .7P#&#G55G#&&&&#BB#&&&&&#BBB&&@&#GGGPP55555555YYYYJJ?????7777!!~~~~~~~^^^^^^^^^^:::::::::::::::::::::::::::::.........................:::::::::::::.::::::::::::^^~!P&@@&&&&&#BBGGG#####&&#####GJ^                                                                                 
#                          .!5B##B55PB&&&&&####&&&&&#BB#&@@#BGGGPPPPP55555YYYYJJ???????777!!~~~!!~~~^^^^^^^^:::::::::::::.::::..:::...............................:::::::::::::::::::::::::^~!?B@@@&&&&&#BBGGG#&&##&&######GJ^                                                                                
#                           ^JB##BP55G#&&&&####&&&&&&#BB&@@&#BGGPPPPP5555555YYYJJ?????????777!!!!!~~~~~^^^^^^^^:::::::::::.......................................:::::::::..::::::::::::::^^~75&@@@&&&&####BBGB&&&#&&####B##GJ^.                                                                              
#                           .!5B#BG55G#&&&&#####&&&&&#BB&&&&&#GGGPPP55555555YYYYYJJJJJJJJJJJJ???777!!!!~~~^^^^^^^^^:::::::....................................:..:::::::::::::::::::::::::^^~JB@@@&&&&&#####BBB#&&&&&&###BB##BY~.                                                                             
#                            .~PB#BGPPB#&&&######&&&&####&&@&&BGGGPP555555555YYYYJJJJJJJYYJJJJYYJJ???777!~~~~~^^^^^^:::::................................::....::::::::::::::::::::::::::^^~7P&@@@&&&&##########&&&&&&&###BBB#B5?^.                                                                           
#                             .7G##BGPG#&&&####B##&&&&####&&&&#BGGGPPP55555555YYYYYYYYYYJJJJYYYYYYYYJJ??777!~~~~~^^^^::::...................::::...::::::::::::::::::::::::::::::::::::::^^!JB@@@@&&&&####&&####&&&&&&&&####BB##B5?^.                                                                         
#                              :JG##BGGB#&&&####B#&&&&&###&&&&&#BGGGGPPPP555555YYYYJYYYYYYYYYY5555555YYYJJ7!!!!~~^^^^^::::.:::...:...:::...:::::::::::::::::::::::::::::::::::::::::::::^^~7P&@@@@&&&&####&&&##&&&&&&&&&&&&##B##&#BGY!^:..                                                                    
#                              .!5B##BBB#&&&&##BB##&&&&####&&&&&#BGBGGPPP55555555YYYYYYYYYYYYYYY555PPP555YJ??77!!!~~^^^:::::::::::...:::::::::::::::::::::::::::::::::::::::::::::::::::^~75#@@@@@&&&&&&#&&&&&&&&&&&&&&&&&&&#####&&&&#GPYJ?7~:                                                                
#                              .^JG#&#####&&&###B##&&&&&&##&&&&@&#BBGGGGPPPP555555YYYYYYJJYYYYY5555PPPPP555YYJJ?77!!!~^^^^^^::::::::::::::::::::::::::::::::::::::::::::::::::::::::::^^^!5#@@@@&@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&##&&&&&&&#BGGG5?^                                                              
#                              .~JG#&&&###&&&&##B##&&&&&&##&&&&&@&#BBBGGGPPPPPP55555YYYYJYYYYYYY555PPPPPPPPP55YYJ???77!!~~~~~^^^^^^^^^^^^^^^^^^^^^:^^^::::::::::::::::::::::::::::::::^^!JB&@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&##BGY~.                                                            
#                              :7YB#&&&&##&&&&#####&&&&&&&&#&&&&&&&#BGGGGPPPPPP555555YYYJJJJYYYY555555PPP5555555YYYYJJ??777!!!~~~~~^^^^^^^^^^^^^^^^^^^::::::::::::::::::::::::::::::^^^!JG&@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&###&&&&#GY~.                                                           
#                             .~JPB#&&&&&&&&&&######&&&&&&&##&&@&&&&#BGGGGGPPPP5555555YYYYJJJYYYYY55YY55555555555PP55YYYJJ???7777!!!!!!!~~~~~~~~^^^^:::::::::::::::::::::::::::::::^^~!?G&@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&####&&#BB#&&#BP7.                                                           
#                             :?PB##&&&&&&&&&&######&&&&&&&##&&&@&&&&&#BGGGGGPPPP5555555YYYYYJJJJJYYYYYY555555555555555YYYYJJJJJJ????77777!!!~~^^::::::::::::::::::::::::::::::::^^~~!?P#@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&####&#BB#&&&B5~.                                                           
#                            :?PB#####&&&&&&&&######&&&&&&&&&&&&&@@@@@&#BGGGGPPPPPP555555YYYYJJJJJJJJJJJJJJYYYYYYYYYYYYYYYYYYJJJJJ????77!!~~^^^^::::::::::::::::::::::::::::::::^^~~7JG&@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&###&&###&&&G7.                                                            
#                           .7G########&&&&&&&#######&&&&&&&&&&&&@@@@@@&#BBGGGGPPPPPPPP5555YYYJJJJ??JJJJJJJJJYYYYYJJJJJJJJJ??????77!!!!~~~^^^^^^^::::::::::::::::::::::::::::::^^~!7YB&@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&###&&&&&&#Y.                                                             
#                          .7P###BBBBB#&&&&&&&######&&&&&&&&&&&&&&@@@@@@&&BBGGGGGGGPPPP55555YYYYJJJJJJJJJJJJJ??JJJ????????777777!!!!!~~~~^^^^^^^^:::::::::::::::::::::^^:^:::^^~!7JP#&@&&&&&@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#&&&&&&&###&&&&&&#J.                                                             
#                         ^JB##BBBGGGB#&&&&&&&######&&&&&&&&&&&&&&&@&&@@@&&#BGGGGGGGGPP555555YYYYYJJJJJJJJJJJ????????777777!!!!!!~~~~~~~^^^^^^^^^^::::::::::::::::::::^^^^^^^~~!7YB&@&&&&&&@@@@&&&&&&&&&&&&&&&&&#&&&&&&&&#&&&##&&&&&&&#&&&&&&&&P^                                                             
#                        ^5BBBGBBG5PB#&&&&&&&&&#####&&&&&&&&&&&&&&&&&&&@@@&#BBBGGGGGGPPPP55555YYYYYYJJJJJJJJ??????77777777!!!!!!!~~~~~~~^^^^^^^::::::::::::::::::^^::::^^^^^~!7JP#&&@&&&&@@@@@@&&&&&&&&&&&&&&&&&##&&&&&&&#&&&&#&&&&&&&#&&&&&&&&&GJ!~~!777~^:..                                                
#                      .!PBBGGBBGPGB#&&&&&&&&&&####&&&&&&&#&&&&&&&&&&&&@@@&&#BBBBBGGGGPPPPPP5555YYYYYYYJJJJJ?????????777!!!!!!!!!~~~~~~^^^^^^^^:::^^^^:::::::^^^^^::^^^^^^~~7JYPB#&&@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&##&&&&&&&&&&&&&&&&&&&&&&&###&&##BPY?!:.                                              
#                     :?GBGGB##BGB#####&&&&&&&&###&&&&&&&&&&&&&&&&&&&&&&&@&&####BBBBBGGGGPPPPP555YYYYYYYYJJJJJ?????77777!!!!!!!~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^~~~!7JY5PG#&@@@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&##&&&&&&&&&&&&&&&&&&&&&&&&&&###&&&&#PY!.                                             
#                   .~5BBGG#&&###BBB##&&&&&&&&####&&&&&&&&&&&&&&&&&&&&@@@@@&&#B##BBBBBGGGGGPPP5555YYYYYYJJJJJ?????77777!!!!!!~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^:^^^^^~~!777?JYPB#&@@@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&###&&&&&&&&&&&&&&&&&&####BBPY?7?JG#&&&#P^                                             
#                  .?GBBBB#&&&##BB##&&&&&&&&&###&&&&&&&&&&&&&&&&&##&&@@@@@@&&##BBBBBBBBBGGGPPP5555YYYYYYYJJJJ?????777777!!!!!!~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^~~~!!77??J5GB#&@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&##&&&&&&&&&&&&&&&&&&&&&&&&&&####BBB#&&&&B?:.                                           
#                 :JGBBB#&&&&####&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&##&&&@@@@@@&&#BBBBBBBBBBGGPPP55555YYYYYJJJJJ?????77777!!!!!!!!~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^~~~~~!!77??YPB#&@@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&#&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#BP5J?!^.                                      
#                :JPP5G#&&&&##&&&&&&#&&&&&&&&&&&&&&&#&&&&&&&&&&&#BB&&@@@@@@@@&&##BBBBBBBBBGGGPPPP5555YYYJJJJ??????7777!!!!!!!!!!!~~~~~~~~~^^^^^^^^^^:::::^^^^^^^~~^^^~~!~~!!!7?Y5P#&@@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#&&&&&&&&&&&&&######&&&&&&&&&&&&&&&&&&#GPGP?:                                    
#               .75J7YB&&&&&&&&&&&##&&&&&&&&&&&&&&&##&&&&&&&&&&#BB#&&@@@&&@@@&&&&#BBGGGGGGGGGGPPP555YYYYYYJJJJJ????77777777!!!!!!!!~~~~~~~^^^^^^^^^^^:^^^^^^^^^~~~~~~~~~~~~~~!7?JYG&@@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&###&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#G5Y5PY^                                   
#               ^JY775#&&&&&&&&&####&&&&&&&&&&&&&&###&&&&&&&&&#BGB#&&@@@@&&&&&&&&&&#GGPGGGGGGGPPPP55555YYYYJJJJJ????7777777!!!!!!!!!!~~~~^^^^^^^^^^^^^^^^^^^^^~^^~~~~~~~~~~^^~~~~YB&@@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#####&&&####&&&&&###########&&&&&&&&&&&&#BPJY5J:                                  
#              .7Y?7YB&&&&&&&&&###&&&&&&&&&&&&&&&&&##&&&&&&&&&BGB#&&@@@@@&&&&&&&&&&&#BGGPPGGGGPPPP555555555YYYJJJJ?????7777!!!!!!!!!!!!~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^~^:~P&@@@@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#####&############BBBBBBGGGB&&&&&&&&&#####BGBP7                                  
#              .7Y??P#&&&&&&&&###&&&&&&&&&&&&&&&&&&##&&&&&&&&#BB##&&@@@@@&&&&&&#&&&&&&&#BGPPPPPPPP555555555555YYYYYJJJJJ???7777777777!!!!~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^~J#@@&&@@@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#&###&&&########BBBB#####BBB#&&&&&&&&&#######B?                                  
#              .!YJ5B&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#&&&&&@&&#BB##&&&@@@@@@&&&&&#BBBB##&&&#GPPPPPP55YYYYYYY5555555555YYYYJJJ?????????777!!~~~~^^^^^^^^^^^^^^^^^^^^^^:^^^^^:^^^:^?B&@@&&&&@@@@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&##&&&&&#########&&&&&&&###&&&&&&&&&&&&&&&&B!                                  
#              .~YPB#&&&&&&&##&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#B###&&&&@@@&&&&&&&&&BGP5PPGBB##BGP5555YJJJJ??JJYYYYYYYYYYYYJJJ?????????777!!!~~~~~^^^^^^^^^^^^^^^:::^^:::::^:::^^:~5&@&&&&&&&@@@@&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#&&&&##&&#######&&&&&&&&&&&&&&&&&&&&&#&&&&&&P^                                  
#              .^YB##&&&&&&##&&&&&&&#B#&&&&&&&&&&&&&&&&&&#######&&&&&&@@&&&&&&&&#G5YY555PG##BP5YYJ?????777??????J???JJ??????77??77777!!!!~~~~^^^^^^^^^^::::::::::::::::::::::^?B@@&&&&&&&&&@&&&&&&&&&&&&&&&&&&&&&&&##&&&&&&&&&&###########&&&&&&&&&&&&&&&&&&&&&&&&####&&&&G!                                  
#        .:^^^~!?5G#&&&&&&&#&&&&&&&#PPB&&&&###&&&&&&&&&&&&&&&&&&&&@@@@@@@@&&&&&&#BP5YYYJ5PB##GYJ???7777777???????77???777777777777777!!!~~~^^^^^^^^^^::::::::::::::::::::::::7G&@@&&&##&@&@&&&&&&&&&&&&&&&&&&&&&&&&&##&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&G!                                 
#     .^?PGBBBBBGGGB#&&&&&&&&&&&&&#G5PB####B##&&&&&&&&&&&&&&&&&&&@@@@@@@@@@&&&&&#GPPPPPPPGB#G5?777777777777777??777777!!!77!!~!!7!!!!!!!!~~^^^^^^^^^::::::::::::::::::::::.:?B&@&@&BG#&&&&&&&&&&&&&&&@@&&&&&&&&&&&&&&#&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&@@@&&&&&&&&&&&&&&&&&&&&#G?.                               
#    .!P#&&&&&&&##B##&&&&&&&&&&&&&#GPPB#BGGB#&&&&&&&###&&&&&&&&&@@@@@@@@@@@&&&&&#GGGB###BGP5YJ?7777!!!!!77!!!777!!!!!!!!!!!!~~~~!~~~~~!!~~~~~^^^^^^^::::::::::::::::::::.:~Y#&@&&&B55#&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#&&&&&&&&&&&&&&&&&&&&&&&&&&&&&@@@&&&&&&&&&&&&&&&&&@&&###G~                               
#   .7G&&&&&&&&&&&&&&&&&&&&&&&&&&&&#BBB#BGPGB#&&&&#BB#&&&&&&&&&@@@&@@@@&&&&&&&&&###&#BP55YJ????7777!~!!!!!!!!!!!!!!!~~~~~~~~~~~~~~~^~~~^^^^^^^^^^^^^:::::::::::::::::::^!YB&&&&&&#G5G#&&&&&&&&#&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#####P:                              
#   ~P##BBB#&&&&&&&&&&&&&&&&&&&&&&&&&&&&#BGGB#&&&#BG#&&&&&&&&@@@@@&&&&&&&&&########BGYJ?????777777!!!!!!~~~~~~!!~~~^^^^~~^^^^^^^^^^^^^^^^^^^^^::::^::::::::::::::::::^!JG&&&&&&&&BGGB&&&&&&&###&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&###&&&&&&&&&&&&&&&&&&&&&&&&&&&##&&&&&&##&&&#?.                             
#   !5PGGB#&&&&&&&&&&&&&&##&&&&&&&&&&&&&&#BBB#&&&###&&&&&&&&&&&&&&&&&&&&&#BBBBB###BP5JJJ??7777777!!!!!!!!!!!!!!~~^^^^^^^^^^^^^^^^^^^^^^^^^^:::::::::::::::::::::^^~~!?P##&&#BG#&#BGG#&&&&&&#B#&&&&&##&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&#&&&&&&&&&&&&&&&#####&&&&##&&&&&P^                             
#   ~J5GB##&&####&&&&&&&&&###&&&&##&&&&&&&&####&&&&&&&&&&&&&&&&&####&&&&&#BGBB###BG5YYYJ?77777!!!!!!!!!!!!!!!~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^:::^:::::::::::::::::^!?YPB&&&BP5Y5PGBP5PB&&&&&&###&&&#BB######&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&###&&&&&##BBB##&###&&###BJ^.                           
#   ~J5B&&&&#BGGB##&&&&&&##B#&&&&&###&&&&&#&###&&&&&&&&&&&&&&&&#BBBB#&&&&&#######GPYJJJ?777!!!!!!!!!!!!!!!~~~~~~~~~~^^^^^^^^^^^^^^^^^^::^^^:::::::::::::::::::^~?5GB##G5?~^~~7JPGY??5#&&&&&&&&&&#BGB###B#&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&###BBB#####&###&B57!~:.                        
#   !5GB&&@&&#BBBB########BGB#&&&&#BB##&&&###&&#&&&&&&&&&&&&&####BGG#&&&&&&&&##BGPYJ??777!!!!!!!!!!!~~~~~~~~~~~~~~^^^^^~~^^^^^^^^^^^^:::::^^::::::::::::::::::^!J55Y?!^...:::^!JYY!^!5#&&&&&&&&&BGB####&&&&&&&&&&&&&&@&&&&&&&&&&&&&&###&&&&&&&#&&&&&&&&&&&&&&&&&#######&&&&&&&&#PY?77!^:.                     
#  :JGGB&&&@&&&&#########BGPB#&&&#BGPPGB##&######&&&&&&&&&&&#BB###BGGB####BBBGGP5YJ?77!!!!!~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^~~~^^^^^^^^::::::::::::::::::::::::....::.......:::::~7?7~~?P#&&###&&#######&&&&#&&&&&&&&&&&&&&&&&&&&&&&&&&&#&&&&&&&&&&&####&&&&&&&&&&####&&&&&&&&&&###GPYJ?77!~:.                  
# .!5GBBBB#&&&&&&&&#####BBBB&&&&#BPJ?JPB##########&&&&&&&&&#BGGB#&#BGPGGGGP555YYJ?77!!~~~~~~~~^^^^^^^^^^^^^:^^^:::^::^^^^^^^^^^^^^^^^::::::::::::::::::::::.................::::^^~~^~!YB####&&&&&###&&&###&&&&&###&&&&&&&&&##&&&&&&&&&&&&&&&&&&&#####&&&&&&&&###################BBGP5J?7777!^:.              
# :~?PB##B###&&&&&&#######&&&&&#G5?7?5G####&&&##B##&&&&&&&#BP55PG#&&BG55PPPP5YJ?77!~~~~^^^^^^^^^:^::::::::^^^^^::::::::^:^^^^^^^^^^^^:::::::::::::::::::::..........:::::..::::::::::^^!J5GB#&&&&&&&&&&&##&&&&#BBBB##&&&&&&&####&&&&&&&&&&&&&&&&&&##&&&&&##&&#####################BBBGP5J??7777!~:.           
#  .^!J5PB###BB#&&&&&&&&#&&&##BPJ77J5GBBGB##&#####&&&&&&&##BBGPGBB###G5Y555P5Y?7!~~^^^^^^^^:::::::::::::::::^^::::::::::::^^^^^^^^^^:::::::::::::::::::::::..........::::...:::::::^^^^^~!?YPB#####&&&&&&&&&&&#BBBB##&&&&&&&&######&&##&&&&&&&&&&&&&&&&&#############################BBGP5YJJ??777!~^:        
#   ..::~?PGPGB&&&&#BGGGGGBB#BGY!!J5GGP55B&&&#BB#&&&&&&#BGPPP55555555PP5YYY555J7!~~^^^^:::::::::::::::::::::::::::::::::::^^^^:^:^::::::::::::::::::::::::::...........:::::::::::::^^~~~!?JY5PGBB##&&&&&&&&&&#BBB##&&&&&&&&###BBB#######&&###&&&&&&&###############BBBBB####BB#######BBBGPP555Y??777!~~:.    
#   ....:75GGG#&&&##BGGGGBB####BGPPGG5Y5B&&&#BBB#&&&&&&#GPP555555YYYYPGGYJJYYYJ?!~~^^^::::::::::...:::::::::::::::::::::::::::^^^::::::::::::::::::::::::::::..::::::::::::::::::::^^~~~~!777?JY5PGB#&&&&&&&&&&###&&&&&&&&&&##BBBBB############################B#BBBBBBBBBBBBBB########BBBGGGPPP5YJ?7!!7!!~^. 
