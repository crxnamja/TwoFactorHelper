#!/usr/bin/env python3
"""
TwoFactorHelper - A macOS menu bar app that monitors iMessage for 2FA codes
and automatically copies them to the clipboard.

Requires: Full Disk Access (System Settings > Privacy & Security > Full Disk Access)
"""

import os
import re
import sqlite3
import subprocess
import time
import threading

import objc
from AppKit import (
    NSApplication,
    NSStatusBar,
    NSMenu,
    NSMenuItem,
    NSImage,
    NSVariableStatusItemLength,
    NSTimer,
    NSRunLoop,
    NSDefaultRunLoopMode,
    NSPasteboard,
    NSPasteboardTypeString,
)
from Foundation import NSDate, NSObject

objc.loadBundle(
    "UserNotifications",
    globals(),
    bundle_path="/System/Library/Frameworks/UserNotifications.framework",
)

from PyObjCTools import AppHelper

# 2FA code patterns - order matters, more specific patterns first
CODE_PATTERNS = [
    # "Your code is 123456" / "verification code: 123456" / "code: 1234"
    re.compile(r'(?:code|passcode|pin)\s*(?:is|:)\s*(\d{4,8})\b', re.IGNORECASE),
    # "123456 is your (verification) code"
    re.compile(r'\b(\d{4,8})\s+is\s+your\s+(?:\w+\s+)?code', re.IGNORECASE),
    # "OTP: 123456" or "OTP is 123456"
    re.compile(r'OTP[:\s]+(\d{4,8})\b', re.IGNORECASE),
    # "G-123456" (Google style)
    re.compile(r'\b(G-\d{4,8})\b'),
    # Context word within 40 chars before a code
    re.compile(
        r'(?:verif|confirm|authent|secur|sign.?in|log.?in|2fa|mfa|one.?time|token)'
        r'[\s\S]{0,40}?\b(\d{4,8})\b',
        re.IGNORECASE,
    ),
    # Code within 40 chars before a context word
    re.compile(
        r'\b(\d{4,8})\b[\s\S]{0,40}?'
        r'(?:verif|confirm|authent|secur|sign.?in|log.?in|2fa|mfa|one.?time|code|token)',
        re.IGNORECASE,
    ),
]

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")


def extract_code(text):
    """Extract a 2FA code from message text."""
    for pattern in CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def send_notification(title, subtitle, body):
    """Send a native macOS notification."""
    content = UNMutableNotificationContent.alloc().init()
    content.setTitle_(title)
    content.setSubtitle_(subtitle)
    content.setBody_(body)
    content.setSound_(UNNotificationSound.defaultSound())

    request = UNNotificationRequest.requestWithIdentifier_content_trigger_(
        str(time.time()), content, None
    )
    center = UNUserNotificationCenter.currentNotificationCenter()
    center.addNotificationRequest_withCompletionHandler_(request, None)


def copy_to_clipboard(text):
    """Copy text to the macOS clipboard."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


def can_access_database():
    """Check if we can read the Messages database."""
    return os.access(DB_PATH, os.R_OK)


class MessageMonitor:
    """Monitors the iMessage database for new 2FA codes."""

    def __init__(self):
        # Start from now - don't process old messages
        # Messages DB stores dates as nanoseconds since 2001-01-01
        # Reference date: 2001-01-01 00:00:00 UTC
        reference_epoch = 978307200  # Unix timestamp of 2001-01-01
        now = time.time()
        seconds_since_ref = now - reference_epoch
        self.last_date = int(seconds_since_ref * 1_000_000_000)

    def check_for_new_code(self):
        """Check for new messages containing 2FA codes.

        Returns (code, message_text) or None.
        """
        try:
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT text, date FROM message
                WHERE date > ? AND text IS NOT NULL AND is_from_me = 0
                ORDER BY date DESC
                LIMIT 10
                """,
                (self.last_date,),
            )

            rows = cursor.fetchall()
            conn.close()

            max_date = self.last_date
            result = None

            for text, date in rows:
                if date > max_date:
                    max_date = date

                if text and result is None:
                    code = extract_code(text)
                    if code:
                        result = (code, text)

            if max_date > self.last_date:
                self.last_date = max_date

            return result

        except (sqlite3.Error, OSError):
            return None


class TwoFactorHelperApp(NSObject):
    """Menu bar application."""

    def init(self):
        self = objc.super(TwoFactorHelperApp, self).init()
        if self is None:
            return None

        self.monitor = MessageMonitor()
        self.last_code = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        # Request notification permission
        center = UNUserNotificationCenter.currentNotificationCenter()
        center.requestAuthorizationWithOptions_completionHandler_(
            0x07, None  # alert | sound | badge
        )

        # Create status bar item
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )

        button = self.status_item.button()
        button.setImage_(
            NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "lock.shield", "2FA Helper"
            )
        )

        # Build menu
        self.menu = NSMenu.alloc().init()

        title_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "2FA Helper", None, ""
        )
        title_item.setEnabled_(False)
        self.menu.addItem_(title_item)
        self.menu.addItem_(NSMenuItem.separatorItem())

        self.status_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Monitoring for codes...", None, ""
        )
        self.status_menu_item.setEnabled_(False)
        self.menu.addItem_(self.status_menu_item)

        self.last_code_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "", "copyLastCode:", ""
        )
        self.last_code_item.setTarget_(self)
        self.last_code_item.setHidden_(True)
        self.menu.addItem_(self.last_code_item)

        self.menu.addItem_(NSMenuItem.separatorItem())

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "terminate:", "q"
        )
        self.menu.addItem_(quit_item)

        self.status_item.setMenu_(self.menu)

        # Check database access
        if not can_access_database():
            self.status_menu_item.setTitle_(
                "Error: Grant Full Disk Access in System Settings"
            )
            send_notification(
                "2FA Helper",
                "Permission Required",
                "Grant Full Disk Access in System Settings > Privacy & Security",
            )
            return

        # Start polling timer (every 2 seconds)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, self, "checkForCodes:", None, True
        )
        NSRunLoop.currentRunLoop().addTimer_forMode_(self.timer, NSDefaultRunLoopMode)

    def checkForCodes_(self, timer):
        """Timer callback to check for new 2FA codes."""
        result = self.monitor.check_for_new_code()
        if result is None:
            return

        code, source = result
        self.last_code = code

        # Copy to clipboard
        copy_to_clipboard(code)

        # Update menu
        self.status_menu_item.setTitle_(f"Copied: {code}")
        self.last_code_item.setTitle_(f"Last code: {code} (click to copy)")
        self.last_code_item.setHidden_(False)

        # Send notification
        preview = source[:60] + ("..." if len(source) > 60 else "")
        send_notification("2FA Code Copied", code, preview)

    @objc.python_method
    def _copy_code(self, code):
        copy_to_clipboard(code)

    def copyLastCode_(self, sender):
        """Menu item action to re-copy the last code."""
        if self.last_code:
            copy_to_clipboard(self.last_code)


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(2)  # NSApplicationActivationPolicyAccessory (hide from dock)

    delegate = TwoFactorHelperApp.alloc().init()
    app.setDelegate_(delegate)

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
