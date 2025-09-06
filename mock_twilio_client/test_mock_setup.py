#!/usr/bin/env python3
"""
Test script to validate mock Twilio client setup
"""

import sys
import subprocess
import importlib.util

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['websockets', 'pyaudio', 'requests']
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
            print(f"❌ Missing package: {package}")
        else:
            print(f"✅ Package installed: {package}")
    
    if missing_packages:
        print(f"\n📦 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_audio_system():
    """Check if audio system is working"""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        
        # Check for input devices
        input_devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                input_devices.append((i, info['name']))
        
        p.terminate()
        
        if input_devices:
            print(f"✅ Found {len(input_devices)} audio input devices:")
            for idx, name in input_devices[:3]:  # Show first 3
                print(f"   - {name}")
            return True
        else:
            print("❌ No audio input devices found")
            return False
            
    except Exception as e:
        print(f"❌ Audio system error: {e}")
        return False

def check_django_server():
    """Check if Django server is running"""
    try:
        import requests
        response = requests.get("http://localhost:8000/", timeout=2)
        print("✅ Django server is running")
        return True
    except requests.exceptions.RequestException:
        print("⚠️  Django server not running (this is OK for setup testing)")
        print("   Start with: cd django-backend && python manage.py runserver")
        return None  # Not critical for setup testing

def main():
    """Run all setup checks"""
    print("🔍 Testing Mock Twilio Client Setup")
    print("=" * 40)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Audio System", check_audio_system),
        ("Django Server", check_django_server),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n📋 Checking {name}...")
        result = check_func()
        results.append((name, result))
    
    print("\n" + "=" * 40)
    print("📊 Setup Check Results:")
    
    all_critical_passed = True
    for name, result in results:
        if result is True:
            print(f"✅ {name}: PASS")
        elif result is False:
            print(f"❌ {name}: FAIL")
            if name != "Django Server":  # Django server is not critical for setup
                all_critical_passed = False
        else:
            print(f"⚠️  {name}: SKIP")
    
    print("\n" + "=" * 40)
    if all_critical_passed:
        print("🎉 Setup looks good! You can run the mock client.")
        print("\n🚀 Next steps:")
        print("1. Start Django: cd django-backend && python manage.py runserver")
        print("2. Run mock client: python mock_twilio_client.py")
    else:
        print("❌ Setup issues found. Please fix the failing checks above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())