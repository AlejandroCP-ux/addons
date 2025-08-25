# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import keyring  # Importamos la librería

# Definimos un nombre de servicio único para nuestra aplicación
KEYRING_SERVICE_NAME = "sgich-scan-agent"

class ConfiguratorApp(tk.Tk):
    """
    Aplicación de Tkinter para configurar los detalles de conexión del agente.
    Ahora guarda la contraseña de forma segura usando keyring.
    """
    def __init__(self, initial_config=None):
        super().__init__()
        self.title("Configuración del Agente de Escaneo")
        self.geometry("400x250")
        self.resizable(False, False)

        self.config_data = initial_config if initial_config else {}
        self.saved = False

        # --- Widgets ---
        tk.Label(self, text="URL de Odoo:", anchor="w").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.url_entry = tk.Entry(self, width=40)
        self.url_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(self, text="Base de Datos:", anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.db_entry = tk.Entry(self, width=40)
        self.db_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(self, text="Usuario:", anchor="w").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.user_entry = tk.Entry(self, width=40)
        self.user_entry.grid(row=2, column=1, padx=10, pady=5)

        tk.Label(self, text="Contraseña / API Key:", anchor="w").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.pass_entry = tk.Entry(self, show="*", width=40)
        self.pass_entry.grid(row=3, column=1, padx=10, pady=5)

        # --- Botones ---
        button_frame = tk.Frame(self)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        save_button = tk.Button(button_frame, text="Guardar y Continuar", command=self.save_config)
        save_button.pack(side="left", padx=10)
        cancel_button = tk.Button(button_frame, text="Cancelar", command=self.cancel)
        cancel_button.pack(side="left", padx=10)

        self.load_initial_config()

    def load_initial_config(self):
        """Carga la configuración. La contraseña se recupera de keyring."""
        odoo_config = self.config_data.get("odoo_config", {})
        username = odoo_config.get("username", "")
        
        self.url_entry.insert(0, odoo_config.get("url", "http://localhost:8067"))
        self.db_entry.insert(0, odoo_config.get("db", ""))
        self.user_entry.insert(0, username)
        
        # Intentamos recuperar la contraseña del keyring si ya existe un usuario
        if username:
            password = keyring.get_password(KEYRING_SERVICE_NAME, username)
            if password:
                self.pass_entry.insert(0, password)

    def save_config(self):
        """Valida, guarda la configuración en JSON (sin contraseña) y la contraseña en keyring."""
        url = self.url_entry.get().strip()
        db = self.db_entry.get().strip()
        user = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()

        if not all([url, db, user, password]):
            messagebox.showerror("Error", "Todos los campos son obligatorios.")
            return

        # Guardamos la contraseña de forma segura en el gestor de credenciales del SO
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, user, password)
            messagebox.showinfo("Éxito", "La contraseña ha sido guardada de forma segura en el sistema.")
        except Exception as e:
            messagebox.showerror("Error de Keyring", f"No se pudo guardar la contraseña de forma segura:\n{e}")
            return

        # El archivo JSON ya NO contendrá la contraseña
        self.config_data = {
            "intervalo_principal_min": self.config_data.get("intervalo_principal_min", 60),
            "intervalo_reintento_min": self.config_data.get("intervalo_reintento_min", 5),
            "odoo_config": {
                "url": url,
                "db": db,
                "username": user,
                # "password" ya no se guarda aquí
            }
        }
        self.saved = True
        self.destroy()

    def cancel(self):
        self.saved = False
        self.destroy()