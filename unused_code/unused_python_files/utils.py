# import json
# import logging
# import sys
# from datetime import datetime
# from enum import Enum
# from typing import Any, Dict, Optional, Union

# # Configure color formatting
# class Colors:
#     RESET = "\033[0m"
#     BOLD = "\033[1m"
#     UNDERLINE = "\033[4m"
    
#     # Foreground colors
#     BLACK = "\033[30m"
#     RED = "\033[31m"
#     GREEN = "\033[32m"
#     YELLOW = "\033[33m"
#     BLUE = "\033[34m"
#     MAGENTA = "\033[35m"
#     CYAN = "\033[36m"
#     WHITE = "\033[37m"
    
#     # Background colors
#     BG_BLACK = "\033[40m"
#     BG_RED = "\033[41m"
#     BG_GREEN = "\033[42m"
#     BG_YELLOW = "\033[43m"
#     BG_BLUE = "\033[44m"
#     BG_MAGENTA = "\033[45m"
#     BG_CYAN = "\033[46m"
#     BG_WHITE = "\033[47m"

# class LogLevel(Enum):
#     DEBUG = (Colors.CYAN, "DEBUG")
#     INFO = (Colors.GREEN, "INFO")
#     EVENT = (Colors.BLUE, "EVENT")
#     WARNING = (Colors.YELLOW, "WARNING")
#     ERROR = (Colors.RED, "ERROR")
#     CRITICAL = (Colors.BG_RED + Colors.WHITE, "CRITICAL")

# class Logger:
#     def __init__(self, app_name: str = "TeleCenter", level: LogLevel = LogLevel.INFO):
#         self.app_name = app_name
#         self.level = level
#         self.handlers = [sys.stdout]
#         self.call_context = {}
    
#     def set_call_context(self, call_sid: str, caller_number: Optional[str] = None):
#         """Set the current call context for logging"""
#         self.call_context = {
#             "call_sid": call_sid,
#             "caller_number": caller_number
#         }
    
#     def clear_call_context(self):
#         """Clear the current call context"""
#         self.call_context = {}
    
#     def _format_json(self, data: Dict[str, Any]) -> str:
#         """Format JSON data with indentation for better readability"""
#         return json.dumps(data, indent=2, default=str, ensure_ascii=False)
    
#     def _get_timestamp(self) -> str:
#         """Get current timestamp formatted for logging"""
#         return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
#     def _format_log(self, level: LogLevel, message: str, data: Optional[Dict[str, Any]] = None, 
#                    category: Optional[str] = None) -> str:
#         """Format a log message with metadata and optional JSON data"""
#         color, level_name = level.value
#         timestamp = self._get_timestamp()
        
#         # Format the header with timestamp, level, and app name
#         header = f"{Colors.BOLD}{timestamp} | {color}{level_name.ljust(7)}{Colors.RESET}{Colors.BOLD} | {self.app_name}"
        
#         # Add category if provided
#         if category:
#             header += f" | {Colors.MAGENTA}{category}{Colors.RESET}{Colors.BOLD}"
        
#         # Add context information if available
#         context_info = ""
#         if self.call_context:
#             call_sid = self.call_context.get("call_sid")
#             caller = self.call_context.get("caller_number")
#             if call_sid:
#                 context_info += f" | SID:{call_sid}"
#             if caller:
#                 context_info += f" | Caller:{caller}"
        
#         # Complete the header
#         header = f"{header}{context_info}{Colors.RESET}"
        
#         # Format the message
#         formatted_message = f"{header}\n{message}"
        
#         # Add formatted JSON data if provided
#         if data:
#             json_str = self._format_json(data)
#             formatted_message += f"\n{Colors.CYAN}DATA:{Colors.RESET}\n{json_str}\n"
        
#         return formatted_message
    
#     def _should_log(self, level: LogLevel) -> bool:
#         """Check if the given log level should be logged based on the current level setting"""
#         level_order = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.EVENT, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]
#         return level_order.index(level) >= level_order.index(self.level)
    
#     def _log(self, level: LogLevel, message: str, data: Optional[Dict[str, Any]] = None, 
#             category: Optional[str] = None):
#         """Internal method to log a message with the given level"""
#         if not self._should_log(level):
#             return
        
#         formatted_message = self._format_log(level, message, data, category)
#         for handler in self.handlers:
#             print(formatted_message, file=handler)
    
#     def debug(self, message: str, data: Optional[Dict[str, Any]] = None, category: Optional[str] = None):
#         """Log a debug message"""
#         self._log(LogLevel.DEBUG, message, data, category)
    
#     def info(self, message: str, data: Optional[Dict[str, Any]] = None, category: Optional[str] = None):
#         """Log an info message"""
#         self._log(LogLevel.INFO, message, data, category)
    
#     def event(self, message: str, data: Optional[Dict[str, Any]] = None, category: Optional[str] = None):
#         """Log an event message - for OpenAI events, Twilio events, etc."""
#         self._log(LogLevel.EVENT, message, data, category)
    
#     def warning(self, message: str, data: Optional[Dict[str, Any]] = None, category: Optional[str] = None):
#         """Log a warning message"""
#         self._log(LogLevel.WARNING, message, data, category)
    
#     def error(self, message: str, data: Optional[Dict[str, Any]] = None, category: Optional[str] = None):
#         """Log an error message"""
#         self._log(LogLevel.ERROR, message, data, category)
    
#     def critical(self, message: str, data: Optional[Dict[str, Any]] = None, category: Optional[str] = None):
#         """Log a critical message"""
#         self._log(LogLevel.CRITICAL, message, data, category)
    
#     def openai_event(self, event_type: str, data: Dict[str, Any]):
#         """Log an OpenAI event with appropriate formatting"""
#         category = "OpenAI"
        
#         # Determine log level based on event type
#         if "error" in event_type:
#             self._log(LogLevel.ERROR, f"OpenAI Event: {event_type}", data, category)
#         elif event_type in ["response.done", "conversation.item.input_audio_transcription.completed"]:
#             self._log(LogLevel.INFO, f"OpenAI Event: {event_type}", data, category)
#         else:
#             self._log(LogLevel.DEBUG, f"OpenAI Event: {event_type}", data, category)
    
#     def twilio_event(self, event_type: str, data: Dict[str, Any]):
#         """Log a Twilio event with appropriate formatting"""
#         category = "Twilio"
#         self._log(LogLevel.EVENT, f"Twilio Event: {event_type}", data, category)
    
#     def function_call(self, function_name: str, args: Dict[str, Any] = None):
#         """Log a function call"""
#         self._log(LogLevel.INFO, f"Function Call: {function_name}", args, "Function")
    
#     def function_result(self, function_name: str, result: Any):
#         """Log a function result"""
#         result_data = result if isinstance(result, dict) else {"result": result}
#         self._log(LogLevel.INFO, f"Function Result: {function_name}", result_data, "Function")
    
#     def transcript(self, speaker: str, message: str):
#         """Log a transcript entry"""
#         self._log(LogLevel.INFO, f"{speaker}: {message}", None, "Transcript")

# # Create a global logger instance
# logger = Logger()

# # Set the default log level (can be changed at runtime)
# def set_log_level(level: Union[LogLevel, str]):
#     """Set the global logger level"""
#     if isinstance(level, str):
#         level = level.upper()
#         for log_level in LogLevel:
#             if log_level.value[1] == level:
#                 logger.level = log_level
#                 return
#         raise ValueError(f"Invalid log level: {level}")
#     else:
#         logger.level = level 