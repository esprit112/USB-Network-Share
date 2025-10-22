"""
USB Network Share - Server Application V3
Enhanced with mDNS broadcasting, priority queuing, TLS encryption, and advanced features
"""

import socket
import threading
import serial
import serial.tools.list_ports
import cv2
import struct
import time
import json
import logging
import ssl
import os
from pathlib import Path
from queue import Queue, PriorityQueue, Empty
import tkinter as tk
from tkinter import scrolledtext, messagebox
from dataclasses import dataclass, asdict
from typing import Optional, List
from enum import Enum

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:
    from tkinter import ttk
    TTKBOOTSTRAP_AVAILABLE = False

try:
    from zeroconf import ServiceInfo, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('usb_server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Fix console encoding for Windows
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configuration directory
if sys.platform == 'win32':
    CONFIG_DIR = Path(os.environ.get('APPDATA', '')) / 'USBNetworkShare'
else:
    CONFIG_DIR = Path.home() / '.config' / 'usb_network_share'

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / 'server_config.json'

# Custom Exceptions
class DeviceError(Exception):
    """Base exception for device-related errors"""
    pass

class DeviceConnectionError(DeviceError):
    """Exception for device connection failures"""
    pass

class DeviceTimeoutError(DeviceError):
    """Exception for device timeout issues"""
    pass

# Connection States
class ConnectionState(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting..."
    CONNECTED = "Connected"
    ERROR = "Error"

# Command Priority Levels
class CommandPriority(Enum):
    EMERGENCY = 0  # Emergency stop, safety interlocks
    HIGH = 1       # G-code commands
    NORMAL = 5     # Regular serial data
    LOW = 10       # Status queries

@dataclass
class ServerConfig:
    """Server configuration"""
    server_name: str = "USB-Share-Server"
    server_port: int = 5555
    use_tls: bool = False
    enable_discovery: bool = True
    last_serial_port: Optional[str] = None
    last_camera_index: int = 0
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(asdict(self), f, indent=2)
            logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    @classmethod
    def load(cls):
        """Load configuration from file"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                logger.info(f"Configuration loaded from {CONFIG_FILE}")
                return cls(**data)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
        return cls()

@dataclass
class DeviceStatus:
    serial_port: Optional[str] = None
    camera_index: Optional[int] = None
    clients_connected: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    uptime: float = 0.0
    packets_sent: int = 0
    packets_received: int = 0
    commands_queued: int = 0

class VideoEncoder:
    """Handles video encoding for efficient streaming"""
    def __init__(self, width=640, height=480, fps=30, quality=80):
        self.width = width
        self.height = height
        self.fps = fps
        self.quality = quality
        
    def encode_frame(self, frame):
        """Encode frame with JPEG compression"""
        # Resize if needed
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))
        
        # Encode to JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
        _, encoded = cv2.imencode('.jpg', frame, encode_param)
        return encoded.tobytes()

class HeartbeatManager:
    """Manages client heartbeats for connection monitoring"""
    def __init__(self, interval=5, timeout=15):
        self.interval = interval
        self.timeout = timeout
        self.last_ping = {}
        self.lock = threading.Lock()
    
    def update_ping(self, client_id):
        """Update last ping time for client"""
        with self.lock:
            self.last_ping[client_id] = time.time()
    
    def is_alive(self, client_id):
        """Check if client is still alive"""
        with self.lock:
            if client_id not in self.last_ping:
                return False
            return (time.time() - self.last_ping[client_id]) < self.timeout
    
    def remove_client(self, client_id):
        """Remove client from tracking"""
        with self.lock:
            self.last_ping.pop(client_id, None)

class PriorityCommandQueue:
    """Priority queue for serial commands"""
    def __init__(self, maxsize=100):
        self.queue = PriorityQueue(maxsize=maxsize)
        self.lock = threading.Lock()
        
    def put(self, priority: CommandPriority, command: bytes, timeout=None):
        """Add command to queue with priority"""
        try:
            self.queue.put((priority.value, time.time(), command), timeout=timeout)
            return True
        except:
            return False
    
    def get(self, timeout=None):
        """Get highest priority command"""
        try:
            priority, timestamp, command = self.queue.get(timeout=timeout)
            return command
        except Empty:
            return None
    
    def size(self):
        """Get current queue size"""
        return self.queue.qsize()
    
    def clear(self):
        """Clear all commands"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                break

class USBServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB Network Share - Server V3")
        self.root.geometry("850x800")
        
        # Load configuration
        self.config = ServerConfig.load()
        
        # Server state
        self.running = False
        self.server_socket = None
        self.clients = {}  # client_socket: client_id
        self.client_threads = {}
        self.serial_port = None
        self.camera = None
        self.camera_thread = None
        self.server_thread = None
        self.heartbeat_thread = None
        self.ssl_context = None
        
        # Priority command queue
        self.command_queue = PriorityCommandQueue()
        self.command_processor_thread = None
        
        # Performance tracking
        self.status = DeviceStatus()
        self.start_time = None
        self.frame_queue = Queue(maxsize=2)
        self.video_encoder = VideoEncoder()
        
        # Heartbeat management
        self.heartbeat_manager = HeartbeatManager()
        
        # mDNS service
        self.zeroconf = None
        self.service_info = None
        
        self.setup_ui()
        self.load_config_to_ui()
        self.update_status_display()
        
    def setup_ui(self):
        """Setup modern UI with ttkbootstrap"""
        if TTKBOOTSTRAP_AVAILABLE:
            style = ttk.Style(theme='darkly')
        else:
            style = ttk.Style()
            style.theme_use('clam')
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="🖥️ USB Network Share Server V3", 
            font=('Segoe UI', 18, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Device Selection Frame
        device_frame = ttk.LabelFrame(main_frame, text="📱 Connected Devices", padding="15")
        device_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # COM Port Selection
        ttk.Label(device_frame, text="COM Port (Laser):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.com_port_var = tk.StringVar()
        self.com_port_combo = ttk.Combobox(
            device_frame, 
            textvariable=self.com_port_var,
            width=35,
            state='readonly'
        )
        self.com_port_combo.grid(row=0, column=1, padx=5, pady=5)
        
        refresh_btn = ttk.Button(
            device_frame, 
            text="🔄 Refresh",
            command=self.refresh_devices,
            bootstyle="info-outline" if TTKBOOTSTRAP_AVAILABLE else None
        )
        refresh_btn.grid(row=0, column=2, padx=5)
        
        # Camera Selection
        ttk.Label(device_frame, text="Camera Index:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.camera_var = tk.StringVar(value=str(self.config.last_camera_index))
        self.camera_spin = ttk.Spinbox(
            device_frame,
            from_=0,
            to=5,
            textvariable=self.camera_var,
            width=33
        )
        self.camera_spin.grid(row=1, column=1, padx=5, pady=5)
        
        # Server Control Frame
        control_frame = ttk.LabelFrame(main_frame, text="⚙️ Server Control", padding="15")
        control_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Server name
        ttk.Label(control_frame, text="Server Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=self.config.server_name)
        ttk.Entry(control_frame, textvariable=self.name_var, width=37).grid(
            row=0, column=1, padx=5, pady=5
        )
        
        # Server port
        ttk.Label(control_frame, text="Server Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.port_var = tk.StringVar(value=str(self.config.server_port))
        ttk.Entry(control_frame, textvariable=self.port_var, width=37).grid(
            row=1, column=1, padx=5, pady=5
        )
        
        # Options
        options_frame = ttk.Frame(control_frame)
        options_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        self.use_tls_var = tk.BooleanVar(value=self.config.use_tls)
        use_tls_cb = ttk.Checkbutton(
            options_frame,
            text="Use TLS encryption",
            variable=self.use_tls_var
        )
        use_tls_cb.pack(side=tk.LEFT, padx=5)
        
        if ZEROCONF_AVAILABLE:
            self.enable_discovery_var = tk.BooleanVar(value=self.config.enable_discovery)
            discovery_cb = ttk.Checkbutton(
                options_frame,
                text="Enable mDNS discovery",
                variable=self.enable_discovery_var
            )
            discovery_cb.pack(side=tk.LEFT, padx=5)
        
        # Start/Stop Button
        self.start_button = ttk.Button(
            control_frame,
            text="▶ Start Server",
            command=self.toggle_server,
            width=25,
            bootstyle="success" if TTKBOOTSTRAP_AVAILABLE else None
        )
        self.start_button.grid(row=3, column=0, columnspan=2, pady=15)
        
        # Connection Status Indicator
        status_indicator_frame = ttk.Frame(control_frame)
        status_indicator_frame.grid(row=4, column=0, columnspan=2, pady=5)
        
        ttk.Label(status_indicator_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_indicator = ttk.Label(
            status_indicator_frame,
            text="⚫ Stopped",
            font=('Segoe UI', 10, 'bold')
        )
        self.status_indicator.pack(side=tk.LEFT)
        
        # Statistics Frame
        stats_frame = ttk.LabelFrame(main_frame, text="📊 Statistics", padding="15")
        stats_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.BOTH, expand=True)
        
        self.clients_label = ttk.Label(stats_grid, text="Clients: 0")
        self.clients_label.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.uptime_label = ttk.Label(stats_grid, text="Uptime: 0s")
        self.uptime_label.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        
        self.data_sent_label = ttk.Label(stats_grid, text="Sent: 0 MB")
        self.data_sent_label.grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.data_recv_label = ttk.Label(stats_grid, text="Received: 0 MB")
        self.data_recv_label.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        self.packets_label = ttk.Label(stats_grid, text="Packets: 0 sent / 0 received")
        self.packets_label.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        
        self.queue_label = ttk.Label(stats_grid, text="Command Queue: 0")
        self.queue_label.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        
        # Status/Log Frame
        log_frame = ttk.LabelFrame(main_frame, text="📝 Server Log", padding="10")
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.status_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            width=85,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        self.log("✓ Server V3 initialized successfully")
        if ZEROCONF_AVAILABLE:
            self.log("✓ mDNS server discovery available")
        else:
            self.log("ℹ Install 'zeroconf' for automatic server discovery")
        self.log("ℹ Select devices and click Start Server to begin")
        
    def load_config_to_ui(self):
        """Load saved configuration into UI"""
        self.name_var.set(self.config.server_name)
        self.port_var.set(str(self.config.server_port))
        self.use_tls_var.set(self.config.use_tls)
        if ZEROCONF_AVAILABLE:
            self.enable_discovery_var.set(self.config.enable_discovery)
        self.camera_var.set(str(self.config.last_camera_index))
    
    def save_config_from_ui(self):
        """Save current UI settings to configuration"""
        self.config.server_name = self.name_var.get()
        self.config.server_port = int(self.port_var.get())
        self.config.use_tls = self.use_tls_var.get()
        if ZEROCONF_AVAILABLE:
            self.config.enable_discovery = self.enable_discovery_var.get()
        self.config.last_camera_index = int(self.camera_var.get())
        if self.serial_port:
            self.config.last_serial_port = self.status.serial_port
        self.config.save()
        
    def refresh_devices(self):
        """Refresh list of available COM ports"""
        try:
            ports = serial.tools.list_ports.comports()
            port_list = [f"{port.device} - {port.description}" for port in ports]
            self.com_port_combo['values'] = port_list
            if port_list:
                # Try to select last used port
                if self.config.last_serial_port:
                    for i, port in enumerate(port_list):
                        if port.startswith(self.config.last_serial_port):
                            self.com_port_combo.current(i)
                            break
                else:
                    self.com_port_combo.current(0)
            self.log(f"✓ Found {len(port_list)} COM port(s)")
        except Exception as e:
            self.log(f"✗ Error refreshing devices: {e}", level="ERROR")
        
    def log(self, message, level="INFO"):
        """Add message to status log"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.status_text.insert(tk.END, log_message)
        self.status_text.see(tk.END)
        
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
        
    def update_status_indicator(self, state: ConnectionState):
        """Update status indicator with color coding"""
        status_map = {
            ConnectionState.DISCONNECTED: ("⚫ Stopped", "gray"),
            ConnectionState.CONNECTING: ("🟡 Starting...", "orange"),
            ConnectionState.CONNECTED: ("🟢 Running", "green"),
            ConnectionState.ERROR: ("🔴 Error", "red")
        }
        
        text, color = status_map.get(state, ("⚫ Unknown", "gray"))
        self.status_indicator.config(text=text)
        
    def update_status_display(self):
        """Update statistics display periodically"""
        if self.running and self.start_time:
            self.status.uptime = time.time() - self.start_time
            self.status.clients_connected = len(self.clients)
            self.status.commands_queued = self.command_queue.size()
            
            self.clients_label.config(text=f"Clients: {self.status.clients_connected}")
            self.uptime_label.config(text=f"Uptime: {int(self.status.uptime)}s")
            self.data_sent_label.config(
                text=f"Sent: {self.status.bytes_sent / 1024 / 1024:.2f} MB"
            )
            self.data_recv_label.config(
                text=f"Received: {self.status.bytes_received / 1024 / 1024:.2f} MB"
            )
            self.packets_label.config(
                text=f"Packets: {self.status.packets_sent} sent / {self.status.packets_received} received"
            )
            self.queue_label.config(
                text=f"Command Queue: {self.status.commands_queued}"
            )
        
        # Schedule next update
        self.root.after(1000, self.update_status_display)
        
    def toggle_server(self):
        """Start or stop the server"""
        if not self.running:
            self.start_server()
        else:
            self.stop_server()
    
    def setup_tls_context(self):
        """Setup TLS context for secure connections"""
        if not self.use_tls_var.get():
            return None
        
        # For production, use real certificates
        # This is a simplified example using self-signed cert
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # In production, load actual certificates:
        # context.load_cert_chain('server.crt', 'server.key')
        
        return context
    
    def start_mdns_service(self):
        """Start mDNS service broadcasting"""
        if not ZEROCONF_AVAILABLE or not self.enable_discovery_var.get():
            return
        
        try:
            server_name = self.name_var.get()
            server_port = int(self.port_var.get())
            
            # Get local IP
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            self.zeroconf = Zeroconf()
            self.service_info = ServiceInfo(
                "_usb-share._tcp.local.",
                f"{server_name}._usb-share._tcp.local.",
                addresses=[socket.inet_aton(local_ip)],
                port=server_port,
                properties={
                    'version': '3.0',
                    'tls': 'true' if self.use_tls_var.get() else 'false'
                }
            )
            self.zeroconf.register_service(self.service_info)
            self.log(f"✓ mDNS service registered: {server_name}")
        except Exception as e:
            logger.error(f"Failed to start mDNS: {e}")
            self.log(f"⚠ mDNS registration failed: {e}", level="WARNING")
    
    def stop_mdns_service(self):
        """Stop mDNS service broadcasting"""
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                self.log("ℹ mDNS service unregistered")
            except:
                pass
            self.zeroconf = None
            self.service_info = None
            
    def start_server(self):
        """Start the server with improved error handling"""
        try:
            self.update_status_indicator(ConnectionState.CONNECTING)
            
            # Save configuration
            self.save_config_from_ui()
            
            # Get selected COM port
            com_selection = self.com_port_var.get()
            if not com_selection:
                raise DeviceConnectionError("No COM port selected")
            
            serial_port_name = com_selection.split(" - ")[0]
            camera_index = int(self.camera_var.get())
            server_port = int(self.port_var.get())
            
            # Open serial port
            try:
                self.serial_port = serial.Serial(
                    serial_port_name,
                    115200,
                    timeout=0.1
                )
                time.sleep(0.1)
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.log(f"✓ Opened serial port: {serial_port_name}")
                self.status.serial_port = serial_port_name
            except serial.SerialException as e:
                raise DeviceConnectionError(f"Failed to open serial port: {e}")
                
            # Open camera
            try:
                self.camera = cv2.VideoCapture(camera_index)
                if not self.camera.isOpened():
                    raise DeviceConnectionError("Failed to open camera")
                
                # Set camera properties
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera.set(cv2.CAP_PROP_FPS, 30)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                self.log(f"✓ Opened camera: {camera_index}")
                self.status.camera_index = camera_index
                
                # Start camera capture thread
                self.camera_thread = threading.Thread(
                    target=self.camera_capture_loop,
                    daemon=True
                )
                self.camera_thread.start()
                
            except Exception as e:
                if self.serial_port:
                    self.serial_port.close()
                raise DeviceConnectionError(f"Failed to open camera: {e}")
            
            # Setup TLS if enabled
            if self.use_tls_var.get():
                self.ssl_context = self.setup_tls_context()
                self.log("✓ TLS encryption configured")
            
            # Start server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            self.server_socket.bind(('0.0.0.0', server_port))
            self.server_socket.listen(5)
            
            self.running = True
            self.start_time = time.time()
            
            # Start command processor thread
            self.command_processor_thread = threading.Thread(
                target=self.process_command_queue,
                daemon=True
            )
            self.command_processor_thread.start()
            
            # Start server thread
            self.server_thread = threading.Thread(
                target=self.accept_connections,
                daemon=True
            )
            self.server_thread.start()
            
            # Start heartbeat thread
            self.heartbeat_thread = threading.Thread(
                target=self.heartbeat_loop,
                daemon=True
            )
            self.heartbeat_thread.start()
            
            # Start mDNS service
            self.start_mdns_service()
            
            self.start_button.config(text="⏹ Stop Server")
            if TTKBOOTSTRAP_AVAILABLE:
                self.start_button.config(bootstyle="danger")
            
            self.update_status_indicator(ConnectionState.CONNECTED)
            self.log(f"✓ Server started on port {server_port}")
            self.log(f"ℹ Server IP: {socket.gethostbyname(socket.gethostname())}")
            self.log("⏳ Waiting for client connections...")
            
        except DeviceError as e:
            self.log(f"✗ Device error: {e}", level="ERROR")
            self.update_status_indicator(ConnectionState.ERROR)
            self.cleanup()
        except Exception as e:
            self.log(f"✗ Error starting server: {e}", level="ERROR")
            self.update_status_indicator(ConnectionState.ERROR)
            self.cleanup()
    
    def process_command_queue(self):
        """Process commands from priority queue"""
        logger.info("Command processor thread started")
        
        while self.running:
            try:
                command = self.command_queue.get(timeout=0.1)
                if command and self.serial_port:
                    self.serial_port.write(command)
                    time.sleep(0.01)  # Small delay between commands
            except:
                continue
        
        logger.info("Command processor thread stopped")
            
    def camera_capture_loop(self):
        """Continuously capture frames in background thread"""
        logger.info("Camera capture thread started")
        
        while self.running and self.camera:
            try:
                ret, frame = self.camera.read()
                if ret:
                    try:
                        self.frame_queue.put_nowait(frame)
                    except:
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait(frame)
                        except:
                            pass
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                logger.error(f"Camera capture error: {e}")
                time.sleep(1)
        
        logger.info("Camera capture thread stopped")
        
    def heartbeat_loop(self):
        """Send periodic heartbeats to check client connections"""
        while self.running:
            try:
                dead_clients = []
                for client_socket, client_id in list(self.clients.items()):
                    if not self.heartbeat_manager.is_alive(client_id):
                        dead_clients.append(client_socket)
                        self.log(f"⚠ Client {client_id} timed out")
                
                for client_socket in dead_clients:
                    self.remove_client(client_socket)
                
                time.sleep(5)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                
    def stop_server(self):
        """Stop the server gracefully"""
        self.running = False
        self.stop_mdns_service()
        self.cleanup()
        self.start_button.config(text="▶ Start Server")
        if TTKBOOTSTRAP_AVAILABLE:
            self.start_button.config(bootstyle="success")
        self.update_status_indicator(ConnectionState.DISCONNECTED)
        self.log("✓ Server stopped")
        
    def cleanup(self):
        """Clean up resources safely"""
        if self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None
            
        if self.camera:
            try:
                self.camera.release()
            except:
                pass
            self.camera = None
            
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
            
        # Close all client connections
        for client_socket in list(self.clients.keys()):
            try:
                client_socket.close()
            except:
                pass
        self.clients.clear()
        self.client_threads.clear()
        
        # Clear command queue
        self.command_queue.clear()
        
    def accept_connections(self):
        """Accept client connections"""
        client_counter = 0
        
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, address = self.server_socket.accept()
                
                # Wrap with TLS if enabled
                if self.ssl_context:
                    try:
                        client_socket = self.ssl_context.wrap_socket(client_socket, server_side=True)
                    except Exception as e:
                        logger.error(f"TLS handshake failed: {e}")
                        client_socket.close()
                        continue
                
                # Enable TCP_NODELAY
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                
                client_counter += 1
                client_id = f"Client-{client_counter}"
                
                self.clients[client_socket] = client_id
                self.heartbeat_manager.update_ping(client_id)
                
                self.log(f"✓ {client_id} connected from {address[0]}:{address[1]}")
                
                # Start handler thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_id),
                    daemon=True
                )
                self.client_threads[client_id] = client_thread
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log(f"✗ Error accepting connection: {e}", level="ERROR")
                    
    def remove_client(self, client_socket):
        """Remove client safely"""
        if client_socket in self.clients:
            client_id = self.clients[client_socket]
            self.heartbeat_manager.remove_client(client_id)
            del self.clients[client_socket]
            self.client_threads.pop(client_id, None)
            try:
                client_socket.close()
            except:
                pass
            self.log(f"ℹ {client_id} disconnected")
                    
    def handle_client(self, client_socket, client_id):
        """Handle a connected client"""
        logger.info(f"Handler started for {client_id}")
        
        try:
            while self.running and client_socket in self.clients:
                try:
                    length_data = self.recv_exact(client_socket, 4)
                    if not length_data:
                        break
                    
                    command_length = struct.unpack("!I", length_data)[0]
                    if command_length > 1024 * 1024:
                        logger.warning(f"Command too large from {client_id}")
                        break
                    
                    command_data = self.recv_exact(client_socket, command_length)
                    if not command_data:
                        break
                    
                    self.status.bytes_received += len(length_data) + len(command_data)
                    self.status.packets_received += 1
                    command = command_data.decode('utf-8').strip()
                    
                    # Update heartbeat
                    self.heartbeat_manager.update_ping(client_id)
                    
                    # Handle commands
                    if command == "PING":
                        self.send_response(client_socket, b"PONG")
                        
                    elif command == "GET_SERIAL":
                        if self.serial_port and self.serial_port.in_waiting:
                            serial_data = self.serial_port.read(self.serial_port.in_waiting)
                            self.send_response(client_socket, serial_data)
                        else:
                            self.send_response(client_socket, b'')
                            
                    elif command.startswith("SEND_SERIAL:"):
                        serial_data = command[12:].encode('latin-1')
                        # Add to priority queue
                        priority = CommandPriority.NORMAL
                        if b'M112' in serial_data or b'!' in serial_data:  # Emergency stop
                            priority = CommandPriority.EMERGENCY
                        elif serial_data.startswith(b'G') or serial_data.startswith(b'M'):
                            priority = CommandPriority.HIGH
                        
                        self.command_queue.put(priority, serial_data)
                        self.send_response(client_socket, b'OK')
                            
                    elif command == "GET_FRAME":
                        try:
                            frame = self.frame_queue.get_nowait()
                            encoded_frame = self.video_encoder.encode_frame(frame)
                            self.send_response(client_socket, encoded_frame)
                        except Empty:
                            self.send_response(client_socket, b'')
                    
                except socket.timeout:
                    continue
                    
        except Exception as e:
            logger.error(f"{client_id} handler error: {e}")
        finally:
            self.remove_client(client_socket)
            logger.info(f"Handler stopped for {client_id}")
    
    def recv_exact(self, sock, length):
        """Receive exact number of bytes"""
        data = b''
        while len(data) < length:
            try:
                sock.settimeout(5.0)
                packet = sock.recv(length - len(data))
                if not packet:
                    return None
                data += packet
            except socket.timeout:
                return None
        return data
    
    def send_response(self, sock, data):
        """Send response with length prefix"""
        try:
            length = struct.pack("!I", len(data))
            sock.sendall(length + data)
            self.status.bytes_sent += len(length) + len(data)
            self.status.packets_sent += 1
        except Exception as e:
            logger.error(f"Send error: {e}")

def main():
    if TTKBOOTSTRAP_AVAILABLE:
        root = ttk.Window(themename="darkly")
    else:
        root = tk.Tk()
        
    app = USBServerApp(root)
    
    def on_closing():
        app.running = False
        app.stop_mdns_service()
        app.cleanup()
        app.save_config_from_ui()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
