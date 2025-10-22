"""
USB Network Share - Client Application V3
Enhanced with configuration persistence, device discovery, TLS encryption, and advanced features
"""

import socket
import threading
import serial
import cv2
import struct
import time
import logging
import random
import json
import ssl
import os
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, messagebox
from PIL import Image, ImageTk
from queue import Queue, Empty
from dataclasses import dataclass, asdict
from typing import Optional
from enum import Enum

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:
    from tkinter import ttk
    TTKBOOTSTRAP_AVAILABLE = False

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('usb_client.log', encoding='utf-8'),
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
CONFIG_FILE = CONFIG_DIR / 'client_config.json'

# Custom Exceptions
class ConnectionError(Exception):
    """Exception for connection failures"""
    pass

class ReconnectionError(Exception):
    """Exception for reconnection failures"""
    pass

# Connection States
class ConnectionState(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting..."
    CONNECTED = "Connected"
    RECONNECTING = "Reconnecting..."
    ERROR = "Error"

@dataclass
class ClientConfig:
    """Client configuration"""
    server_ip: str = "192.168.1.100"
    server_port: int = 5555
    virtual_com_port: str = "COM10"
    auto_reconnect: bool = True
    use_tls: bool = False
    auto_discover: bool = True
    last_server_name: Optional[str] = None
    
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
class ClientStatus:
    server_ip: Optional[str] = None
    server_port: Optional[int] = None
    reconnect_attempts: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    uptime: float = 0.0
    latency_ms: float = 0.0
    packets_sent: int = 0
    packets_received: int = 0
    reconnections: int = 0

@dataclass
class PerformanceMetrics:
    """Detailed performance metrics"""
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    packet_loss_rate: float = 0.0
    frame_rate: float = 0.0
    last_100_latencies: list = None
    
    def __post_init__(self):
        if self.last_100_latencies is None:
            self.last_100_latencies = []
    
    def update_latency(self, latency_ms):
        """Update latency metrics"""
        self.last_100_latencies.append(latency_ms)
        if len(self.last_100_latencies) > 100:
            self.last_100_latencies.pop(0)
        
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.avg_latency_ms = sum(self.last_100_latencies) / len(self.last_100_latencies)

class ReconnectionManager:
    """Manages auto-reconnection with exponential backoff"""
    def __init__(self, base_delay=1.0, max_delay=60.0, jitter=0.1):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.attempt = 0
        
    def get_delay(self):
        """Calculate next reconnection delay with exponential backoff and jitter"""
        delay = min(self.base_delay * (2 ** self.attempt), self.max_delay)
        jitter_amount = delay * self.jitter * (random.random() * 2 - 1)
        return delay + jitter_amount
    
    def increment(self):
        """Increment attempt counter"""
        self.attempt += 1
    
    def reset(self):
        """Reset attempt counter on successful connection"""
        self.attempt = 0

class ServerDiscoveryListener(ServiceListener):
    """mDNS service discovery listener"""
    def __init__(self, callback):
        self.callback = callback
        self.servers = {}
    
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            address = socket.inet_ntoa(info.addresses[0])
            port = info.port
            server_name = name.split('.')[0]
            self.servers[server_name] = (address, port)
            self.callback('add', server_name, address, port)
    
    def remove_service(self, zc, type_, name):
        server_name = name.split('.')[0]
        if server_name in self.servers:
            del self.servers[server_name]
            self.callback('remove', server_name, None, None)
    
    def update_service(self, zc, type_, name):
        pass

class USBClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("USB Network Share - Client V3")
        self.root.geometry("900x850")
        
        # Load configuration
        self.config = ClientConfig.load()
        
        # Client state
        self.connected = False
        self.client_socket = None
        self.virtual_com_port = None
        self.ssl_context = None
        
        # Performance tracking
        self.status = ClientStatus()
        self.metrics = PerformanceMetrics()
        self.start_time = None
        self.last_ping_time = 0
        
        # Threads
        self.serial_thread = None
        self.camera_thread = None
        self.heartbeat_thread = None
        self.reconnect_thread = None
        self.running = False
        
        # Reconnection
        self.reconnection_manager = ReconnectionManager()
        self.should_reconnect = False
        
        # Frame display
        self.current_frame = None
        
        # Server discovery
        self.zeroconf = None
        self.browser = None
        self.discovered_servers = {}
        
        self.setup_ui()
        self.load_config_to_ui()
        
        if self.config.auto_discover and ZEROCONF_AVAILABLE:
            self.start_discovery()
        
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
            text="💻 USB Network Share Client V3",
            font=('Segoe UI', 18, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Server Discovery Frame (if available)
        if ZEROCONF_AVAILABLE:
            discovery_frame = ttk.LabelFrame(main_frame, text="🔍 Discovered Servers", padding="10")
            discovery_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
            
            self.server_listbox = tk.Listbox(discovery_frame, height=3, font=('Segoe UI', 9))
            self.server_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
            self.server_listbox.bind('<<ListboxSelect>>', self.on_server_selected)
            
            discover_btn = ttk.Button(
                discovery_frame,
                text="🔄 Refresh Discovery",
                command=self.refresh_discovery,
                bootstyle="info" if TTKBOOTSTRAP_AVAILABLE else None
            )
            discover_btn.pack(pady=5)
        
        # Connection Frame
        conn_frame = ttk.LabelFrame(main_frame, text="🌐 Server Connection", padding="15")
        conn_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Server IP
        ttk.Label(conn_frame, text="Server IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ip_var = tk.StringVar(value=self.config.server_ip)
        ttk.Entry(conn_frame, textvariable=self.ip_var, width=37).grid(
            row=0, column=1, padx=5, pady=5
        )
        
        # Server Port
        ttk.Label(conn_frame, text="Server Port:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.port_var = tk.StringVar(value=str(self.config.server_port))
        ttk.Entry(conn_frame, textvariable=self.port_var, width=37).grid(
            row=1, column=1, padx=5, pady=5
        )
        
        # Virtual COM Port
        ttk.Label(conn_frame, text="Virtual COM Port:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.vcom_var = tk.StringVar(value=self.config.virtual_com_port)
        ttk.Entry(conn_frame, textvariable=self.vcom_var, width=37).grid(
            row=2, column=1, padx=5, pady=5
        )
        
        # Options
        options_frame = ttk.Frame(conn_frame)
        options_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        self.auto_reconnect_var = tk.BooleanVar(value=self.config.auto_reconnect)
        auto_reconnect_cb = ttk.Checkbutton(
            options_frame,
            text="Auto-reconnect",
            variable=self.auto_reconnect_var,
            command=self.toggle_auto_reconnect
        )
        auto_reconnect_cb.pack(side=tk.LEFT, padx=5)
        
        self.use_tls_var = tk.BooleanVar(value=self.config.use_tls)
        use_tls_cb = ttk.Checkbutton(
            options_frame,
            text="Use TLS encryption",
            variable=self.use_tls_var
        )
        use_tls_cb.pack(side=tk.LEFT, padx=5)
        
        # Connect/Disconnect Button
        self.connect_button = ttk.Button(
            conn_frame,
            text="🔌 Connect to Server",
            command=self.toggle_connection,
            width=25,
            bootstyle="success" if TTKBOOTSTRAP_AVAILABLE else None
        )
        self.connect_button.grid(row=4, column=0, columnspan=2, pady=15)
        
        # Connection Status Indicator
        status_indicator_frame = ttk.Frame(conn_frame)
        status_indicator_frame.grid(row=5, column=0, columnspan=2, pady=5)
        
        ttk.Label(status_indicator_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_indicator = ttk.Label(
            status_indicator_frame,
            text="⚫ Disconnected",
            font=('Segoe UI', 10, 'bold')
        )
        self.status_indicator.pack(side=tk.LEFT)
        
        # Statistics Frame
        stats_frame = ttk.LabelFrame(main_frame, text="📊 Statistics", padding="15")
        stats_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.BOTH, expand=True)
        
        self.uptime_label = ttk.Label(stats_grid, text="Connected: 0s")
        self.uptime_label.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.latency_label = ttk.Label(stats_grid, text="Latency: 0ms (avg: 0ms)")
        self.latency_label.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        
        self.data_sent_label = ttk.Label(stats_grid, text="Sent: 0 MB")
        self.data_sent_label.grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.data_recv_label = ttk.Label(stats_grid, text="Received: 0 MB")
        self.data_recv_label.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        self.packets_label = ttk.Label(stats_grid, text="Packets: 0 sent / 0 received")
        self.packets_label.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        
        self.reconnect_label = ttk.Label(stats_grid, text="Reconnections: 0")
        self.reconnect_label.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        
        # Camera Display Frame
        camera_frame = ttk.LabelFrame(main_frame, text="📹 Remote Camera Feed", padding="10")
        camera_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.camera_label = ttk.Label(
            camera_frame,
            text="Not Connected",
            background='black',
            foreground='white',
            font=('Segoe UI', 12)
        )
        self.camera_label.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Status Frame
        status_frame = ttk.LabelFrame(main_frame, text="📝 Client Log", padding="10")
        status_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.status_text = scrolledtext.ScrolledText(
            status_frame,
            height=8,
            width=90,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        self.log("✓ Client V3 initialized successfully")
        if ZEROCONF_AVAILABLE:
            self.log("✓ Server discovery enabled")
        else:
            self.log("ℹ Install 'zeroconf' for automatic server discovery")
        self.log("ℹ Enter server details and click Connect")
        
    def load_config_to_ui(self):
        """Load saved configuration into UI"""
        self.ip_var.set(self.config.server_ip)
        self.port_var.set(str(self.config.server_port))
        self.vcom_var.set(self.config.virtual_com_port)
        self.auto_reconnect_var.set(self.config.auto_reconnect)
        self.use_tls_var.set(self.config.use_tls)
    
    def save_config_from_ui(self):
        """Save current UI settings to configuration"""
        self.config.server_ip = self.ip_var.get()
        self.config.server_port = int(self.port_var.get())
        self.config.virtual_com_port = self.vcom_var.get()
        self.config.auto_reconnect = self.auto_reconnect_var.get()
        self.config.use_tls = self.use_tls_var.get()
        self.config.save()
    
    def start_discovery(self):
        """Start mDNS server discovery"""
        if not ZEROCONF_AVAILABLE:
            return
        
        try:
            self.zeroconf = Zeroconf()
            listener = ServerDiscoveryListener(self.on_server_discovered)
            self.browser = ServiceBrowser(self.zeroconf, "_usb-share._tcp.local.", listener)
            self.log("✓ Server discovery started")
        except Exception as e:
            logger.error(f"Failed to start discovery: {e}")
            self.log(f"⚠ Server discovery failed: {e}", level="WARNING")
    
    def refresh_discovery(self):
        """Refresh server discovery"""
        if self.zeroconf:
            try:
                self.zeroconf.close()
            except:
                pass
        self.discovered_servers.clear()
        self.server_listbox.delete(0, tk.END)
        self.start_discovery()
    
    def on_server_discovered(self, action, name, address, port):
        """Handle discovered server"""
        if action == 'add':
            self.discovered_servers[name] = (address, port)
            self.server_listbox.insert(tk.END, f"{name} ({address}:{port})")
            self.log(f"✓ Discovered server: {name} at {address}:{port}")
        elif action == 'remove':
            if name in self.discovered_servers:
                del self.discovered_servers[name]
                # Update listbox
                for i in range(self.server_listbox.size()):
                    if self.server_listbox.get(i).startswith(name):
                        self.server_listbox.delete(i)
                        break
                self.log(f"ℹ Server removed: {name}")
    
    def on_server_selected(self, event):
        """Handle server selection from discovery"""
        selection = self.server_listbox.curselection()
        if selection:
            server_text = self.server_listbox.get(selection[0])
            server_name = server_text.split(' (')[0]
            if server_name in self.discovered_servers:
                address, port = self.discovered_servers[server_name]
                self.ip_var.set(address)
                self.port_var.set(str(port))
                self.log(f"✓ Selected server: {server_name}")
    
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
            ConnectionState.DISCONNECTED: ("⚫ Disconnected", "gray"),
            ConnectionState.CONNECTING: ("🟡 Connecting...", "orange"),
            ConnectionState.CONNECTED: ("🟢 Connected", "green"),
            ConnectionState.RECONNECTING: ("🟠 Reconnecting...", "orange"),
            ConnectionState.ERROR: ("🔴 Error", "red")
        }
        
        text, color = status_map.get(state, ("⚫ Unknown", "gray"))
        self.status_indicator.config(text=text)
    
    def update_status_display(self):
        """Update statistics display periodically"""
        if self.connected and self.start_time:
            self.status.uptime = time.time() - self.start_time
            
            self.uptime_label.config(text=f"Connected: {int(self.status.uptime)}s")
            self.latency_label.config(
                text=f"Latency: {self.status.latency_ms:.1f}ms "
                     f"(avg: {self.metrics.avg_latency_ms:.1f}ms, "
                     f"min: {self.metrics.min_latency_ms:.1f}ms, "
                     f"max: {self.metrics.max_latency_ms:.1f}ms)"
            )
            self.data_sent_label.config(
                text=f"Sent: {self.status.bytes_sent / 1024 / 1024:.2f} MB"
            )
            self.data_recv_label.config(
                text=f"Received: {self.status.bytes_received / 1024 / 1024:.2f} MB"
            )
            self.packets_label.config(
                text=f"Packets: {self.status.packets_sent} sent / {self.status.packets_received} received"
            )
            self.reconnect_label.config(
                text=f"Reconnections: {self.status.reconnections}"
            )
        
        # Schedule next update
        self.root.after(1000, self.update_status_display)
    
    def toggle_auto_reconnect(self):
        """Toggle auto-reconnect feature"""
        self.config.auto_reconnect = self.auto_reconnect_var.get()
        if self.config.auto_reconnect:
            self.log("✓ Auto-reconnect enabled")
        else:
            self.log("ℹ Auto-reconnect disabled")
        self.save_config_from_ui()
        
    def toggle_connection(self):
        """Connect or disconnect from server"""
        if not self.connected:
            self.connect_to_server()
        else:
            self.disconnect_from_server()
            
    def setup_tls_context(self):
        """Setup TLS context for secure connection"""
        if not self.use_tls_var.get():
            return None
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # For self-signed certificates
        return context
            
    def connect_to_server(self):
        """Connect to the server with improved error handling"""
        try:
            self.update_status_indicator(ConnectionState.CONNECTING)
            
            # Save configuration
            self.save_config_from_ui()
            
            server_ip = self.ip_var.get()
            server_port = int(self.port_var.get())
            virtual_com_name = self.vcom_var.get()
            
            self.log(f"⏳ Connecting to {server_ip}:{server_port}...")
            
            # Connect to server with timeout
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_socket.settimeout(10.0)
            
            # Enable TCP_NODELAY for low latency
            raw_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            raw_socket.connect((server_ip, server_port))
            
            # Wrap with TLS if enabled
            if self.use_tls_var.get():
                self.ssl_context = self.setup_tls_context()
                self.client_socket = self.ssl_context.wrap_socket(raw_socket, server_hostname=server_ip)
                self.log("✓ TLS encryption enabled")
            else:
                self.client_socket = raw_socket
            
            self.client_socket.settimeout(None)  # Remove timeout after connection
            
            self.log(f"✓ Connected to server at {server_ip}:{server_port}")
            
            # Open virtual COM port
            try:
                self.virtual_com_port = serial.Serial(
                    virtual_com_name,
                    115200,
                    timeout=0.1
                )
                time.sleep(0.1)
                self.virtual_com_port.reset_input_buffer()
                self.virtual_com_port.reset_output_buffer()
                self.log(f"✓ Opened virtual COM port: {virtual_com_name}")
            except serial.SerialException as e:
                self.log(f"✗ Could not open virtual COM port {virtual_com_name}", level="ERROR")
                self.log(f"⚠ Make sure com0com is installed and configured!", level="WARNING")
                self.log(f"Error: {e}", level="ERROR")
                self.disconnect_from_server()
                return
            
            # Connection successful
            self.connected = True
            self.start_time = time.time()
            self.should_reconnect = True
            self.reconnection_manager.reset()
            
            # Update status
            self.status.server_ip = server_ip
            self.status.server_port = server_port
            
            # Reset metrics
            self.metrics = PerformanceMetrics()
            
            # Start communication threads
            self.running = True
            
            self.serial_thread = threading.Thread(target=self.handle_serial, daemon=True)
            self.camera_thread = threading.Thread(target=self.handle_camera, daemon=True)
            self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
            
            self.serial_thread.start()
            self.camera_thread.start()
            self.heartbeat_thread.start()
            
            self.connect_button.config(text="🔌 Disconnect")
            if TTKBOOTSTRAP_AVAILABLE:
                self.connect_button.config(bootstyle="danger")
            
            self.update_status_indicator(ConnectionState.CONNECTED)
            self.log("✓ Device forwarding active!")
            
        except socket.timeout:
            self.log(f"✗ Connection timeout - server not responding", level="ERROR")
            self.update_status_indicator(ConnectionState.ERROR)
            self.disconnect_from_server()
        except ConnectionRefusedError:
            self.log(f"✗ Connection refused - is the server running?", level="ERROR")
            self.update_status_indicator(ConnectionState.ERROR)
            self.disconnect_from_server()
        except Exception as e:
            self.log(f"✗ Connection error: {e}", level="ERROR")
            self.update_status_indicator(ConnectionState.ERROR)
            self.disconnect_from_server()
            
    def disconnect_from_server(self):
        """Disconnect from server"""
        self.running = False
        self.connected = False
        self.should_reconnect = False
        
        if self.virtual_com_port:
            try:
                self.virtual_com_port.close()
            except:
                pass
            self.virtual_com_port = None
            
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
            
        self.connect_button.config(text="🔌 Connect to Server")
        if TTKBOOTSTRAP_AVAILABLE:
            self.connect_button.config(bootstyle="success")
        
        self.camera_label.config(image='', text='Not Connected')
        self.update_status_indicator(ConnectionState.DISCONNECTED)
        self.log("ℹ Disconnected from server")
    
    def attempt_reconnection(self):
        """Attempt to reconnect with exponential backoff"""
        self.log("🔄 Auto-reconnect triggered")
        self.update_status_indicator(ConnectionState.RECONNECTING)
        self.status.reconnections += 1
        
        while self.should_reconnect and self.config.auto_reconnect and not self.connected:
            delay = self.reconnection_manager.get_delay()
            self.status.reconnect_attempts += 1
            
            self.log(f"⏳ Reconnecting in {delay:.1f}s (attempt #{self.status.reconnect_attempts})...")
            time.sleep(delay)
            
            if not self.should_reconnect:
                break
            
            try:
                self.connect_to_server()
                if self.connected:
                    self.log("✓ Reconnection successful!")
                    return
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
            
            self.reconnection_manager.increment()
            
        self.update_status_indicator(ConnectionState.DISCONNECTED)
        
    def heartbeat_loop(self):
        """Send periodic heartbeats to server"""
        while self.running and self.connected:
            try:
                # Measure latency
                ping_start = time.time()
                
                # Send PING
                self.send_command(b"PING")
                response = self.recv_response()
                
                if response == b"PONG":
                    latency = (time.time() - ping_start) * 1000  # Convert to ms
                    self.status.latency_ms = latency
                    self.metrics.update_latency(latency)
                else:
                    # No response or bad response
                    raise ConnectionError("Heartbeat failed")
                
                time.sleep(5)  # Ping every 5 seconds
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                if self.connected:
                    self.log("⚠ Connection lost - heartbeat failed", level="WARNING")
                    self.handle_disconnect()
                break
    
    def handle_disconnect(self):
        """Handle unexpected disconnection"""
        was_connected = self.connected
        self.running = False
        self.connected = False
        
        if self.virtual_com_port:
            try:
                self.virtual_com_port.close()
            except:
                pass
            self.virtual_com_port = None
            
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        if was_connected and self.config.auto_reconnect and self.should_reconnect:
            # Start reconnection in background thread
            self.reconnect_thread = threading.Thread(
                target=self.attempt_reconnection,
                daemon=True
            )
            self.reconnect_thread.start()
        else:
            self.update_status_indicator(ConnectionState.DISCONNECTED)
        
    def handle_serial(self):
        """Handle serial port forwarding"""
        logger.info("Serial handler thread started")
        
        while self.running and self.connected:
            try:
                # Check if Lightburn sent data to virtual COM port
                if self.virtual_com_port and self.virtual_com_port.in_waiting:
                    data = self.virtual_com_port.read(self.virtual_com_port.in_waiting)
                    
                    # Send to server
                    command = f"SEND_SERIAL:{data.decode('latin-1')}"
                    self.send_command(command.encode('utf-8'))
                    
                    # Get response
                    response = self.recv_response()
                
                # Request data from server's real COM port
                self.send_command(b"GET_SERIAL")
                data = self.recv_response()
                
                # Write to virtual COM port for Lightburn to read
                if data and self.virtual_com_port:
                    self.virtual_com_port.write(data)
                    
                time.sleep(0.01)  # Small delay
                
            except Exception as e:
                if self.running:
                    logger.error(f"Serial communication error: {e}")
                    self.handle_disconnect()
                break
        
        logger.info("Serial handler thread stopped")
                
    def handle_camera(self):
        """Handle camera frame forwarding"""
        logger.info("Camera handler thread started")
        frame_count = 0
        frame_start_time = time.time()
        
        while self.running and self.connected:
            try:
                # Request frame from server
                self.send_command(b"GET_FRAME")
                frame_data = self.recv_response()
                
                if frame_data and len(frame_data) > 0:
                    # Decode JPEG frame
                    import numpy as np
                    nparr = np.frombuffer(frame_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        # Display frame
                        self.display_frame(frame)
                        
                        # Calculate frame rate
                        frame_count += 1
                        if frame_count % 30 == 0:
                            elapsed = time.time() - frame_start_time
                            self.metrics.frame_rate = 30 / elapsed
                            frame_start_time = time.time()
                            frame_count = 0
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                if self.running:
                    logger.error(f"Camera communication error: {e}")
                    self.handle_disconnect()
                break
        
        logger.info("Camera handler thread stopped")
    
    def send_command(self, command):
        """Send command with length prefix"""
        if not self.client_socket:
            raise ConnectionError("Not connected")
        
        if isinstance(command, str):
            command = command.encode('utf-8')
        
        length = struct.pack("!I", len(command))
        self.client_socket.sendall(length + command)
        self.status.bytes_sent += len(length) + len(command)
        self.status.packets_sent += 1
    
    def recv_response(self):
        """Receive response with length prefix"""
        if not self.client_socket:
            raise ConnectionError("Not connected")
        
        # Receive length
        length_data = self.recv_exact(4)
        if not length_data:
            raise ConnectionError("Connection closed")
        
        length = struct.unpack("!I", length_data)[0]
        
        # Sanity check
        if length > 10 * 1024 * 1024:  # 10MB
            raise ConnectionError("Response too large")
        
        # Receive data
        data = self.recv_exact(length)
        self.status.bytes_received += len(length_data) + len(data)
        self.status.packets_received += 1
        
        return data
    
    def recv_exact(self, length):
        """Receive exact number of bytes"""
        data = b''
        while len(data) < length:
            try:
                self.client_socket.settimeout(10.0)
                packet = self.client_socket.recv(length - len(data))
                if not packet:
                    return None
                data += packet
            except socket.timeout:
                raise ConnectionError("Receive timeout")
        return data
        
    def display_frame(self, frame):
        """Display camera frame in GUI"""
        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Resize for display
            height, width = frame_rgb.shape[:2]
            max_width = 800
            if width > max_width:
                scale = max_width / width
                new_width = max_width
                new_height = int(height * scale)
                frame_rgb = cv2.resize(frame_rgb, (new_width, new_height))
            
            # Convert to PhotoImage
            img = Image.fromarray(frame_rgb)
            photo = ImageTk.PhotoImage(image=img)
            
            # Update label (must be done in main thread)
            self.camera_label.config(image=photo, text='')
            self.camera_label.image = photo
            
        except Exception as e:
            logger.error(f"Display frame error: {e}")
    
    def cleanup(self):
        """Cleanup on exit"""
        self.running = False
        self.should_reconnect = False
        self.disconnect_from_server()
        
        if self.zeroconf:
            try:
                self.zeroconf.close()
            except:
                pass
        
        self.save_config_from_ui()

def main():
    if TTKBOOTSTRAP_AVAILABLE:
        root = ttk.Window(themename="darkly")
    else:
        root = tk.Tk()
        
    app = USBClientApp(root)
    
    def on_closing():
        app.cleanup()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
