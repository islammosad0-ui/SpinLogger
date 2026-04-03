#import "SLJailbreakBypass.h"
#import <objc/runtime.h>
#import <UIKit/UIKit.h>

// ---------------------------------------------------------------------------
//  Jailbreak Detection Bypass — mirrors One.dylib's JailbreakDetector_v3
//
//  Hooks NSFileManager and UIApplication to hide jailbreak indicators.
//  This prevents Coin Master from detecting sideloaded/jailbroken environments.
// ---------------------------------------------------------------------------

#pragma mark - Suspicious paths list

static NSArray<NSString *> *SLSuspiciousPaths(void) {
    static NSArray *paths;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        paths = @[
            @"/Applications/Cydia.app",
            @"/Applications/Installer.app",
            @"/Applications/Sileo.app",
            @"/Applications/Zebra.app",
            @"/Library/MobileSubstrate/DynamicLibraries",
            @"/Library/MobileSubstrate/MobileSubstrate.dylib",
            @"/Library/Ringtones",
            @"/Library/Wallpaper",
            @"/System/Library/LaunchDaemons/com.saurik.Cydia.Startup.plist",
            @"/bin/bash",
            @"/bin/sh",
            @"/etc/apt",
            @"/private/var/lib/apt/",
            @"/private/var/lib/cydia",
            @"/private/var/stash",
            @"/private/var/tmp/cydia.log",
            @"/usr/arm-apple-darwin9",
            @"/usr/bin/cycript",
            @"/usr/bin/frida-server",
            @"/usr/include",
            @"/usr/lib/frida",
            @"/usr/lib/libcycript.dylib",
            @"/usr/libexec",
            @"/usr/libexec/cydia",
            @"/usr/local/bin/cycript",
            @"/usr/local/bin/frida-server",
            @"/usr/sbin/frida-server",
            @"/usr/sbin/sshd",
            @"/usr/share",
            @"/var/cache/apt",
            @"/var/lib/cydia",
            @"/var/log/syslog",
            @"/var/run/frida"
        ];
    });
    return paths;
}

static BOOL SLIsSuspiciousPath(NSString *path) {
    if (!path) return NO;
    for (NSString *sus in SLSuspiciousPaths()) {
        if ([path hasPrefix:sus]) return YES;
    }
    // Also block frida/cycript related dylib checks
    if ([path containsString:@"frida"] || [path containsString:@"cycript"]) return YES;
    return NO;
}

#pragma mark - NSFileManager hooks

static IMP sOrig_fileExistsAtPath = NULL;
static IMP sOrig_fileExistsAtPathIsDir = NULL;
static IMP sOrig_isReadableFileAtPath = NULL;

static BOOL SL_fileExistsAtPath(id self, SEL _cmd, NSString *path) {
    if (SLIsSuspiciousPath(path)) return NO;
    return ((BOOL(*)(id, SEL, NSString *))sOrig_fileExistsAtPath)(self, _cmd, path);
}

static BOOL SL_fileExistsAtPathIsDir(id self, SEL _cmd, NSString *path, BOOL *isDir) {
    if (SLIsSuspiciousPath(path)) return NO;
    return ((BOOL(*)(id, SEL, NSString *, BOOL *))sOrig_fileExistsAtPathIsDir)(self, _cmd, path, isDir);
}

static BOOL SL_isReadableFileAtPath(id self, SEL _cmd, NSString *path) {
    if (SLIsSuspiciousPath(path)) return NO;
    return ((BOOL(*)(id, SEL, NSString *))sOrig_isReadableFileAtPath)(self, _cmd, path);
}

#pragma mark - UIApplication canOpenURL: hook

static IMP sOrig_canOpenURL = NULL;

static BOOL SL_canOpenURL(id self, SEL _cmd, NSURL *url) {
    NSString *scheme = url.scheme.lowercaseString;
    if ([scheme isEqualToString:@"cydia"] ||
        [scheme isEqualToString:@"sileo"] ||
        [scheme isEqualToString:@"zbra"] ||
        [scheme isEqualToString:@"filza"]) {
        return NO;
    }
    return ((BOOL(*)(id, SEL, NSURL *))sOrig_canOpenURL)(self, _cmd, url);
}

#pragma mark - C-level fopen/stat/access hooks via method swizzling on NSURL

// Hook NSURL fileURLWithPath: to filter suspicious paths from URL creation checks
static IMP sOrig_contentsOfDirAtPath = NULL;

static NSArray *SL_contentsOfDirAtPath(id self, SEL _cmd, NSString *path, NSError **error) {
    if (SLIsSuspiciousPath(path)) {
        if (error) *error = [NSError errorWithDomain:NSCocoaErrorDomain code:NSFileNoSuchFileError userInfo:nil];
        return nil;
    }
    return ((NSArray *(*)(id, SEL, NSString *, NSError **))sOrig_contentsOfDirAtPath)(self, _cmd, path, error);
}

#pragma mark - fork() detection bypass

// Some apps use fork() to detect jailbreak. On non-jailbroken devices fork() returns -1.
// We don't hook fork() directly since it's a C function — instead we handle it through
// the NSTask/posix_spawn path.

#pragma mark - Install

void SLJailbreakBypassInstall(void) {
    Class fmCls = [NSFileManager class];

    // fileExistsAtPath:
    {
        SEL sel = @selector(fileExistsAtPath:);
        Method m = class_getInstanceMethod(fmCls, sel);
        if (m) {
            sOrig_fileExistsAtPath = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_fileExistsAtPath);
        }
    }

    // fileExistsAtPath:isDirectory:
    {
        SEL sel = @selector(fileExistsAtPath:isDirectory:);
        Method m = class_getInstanceMethod(fmCls, sel);
        if (m) {
            sOrig_fileExistsAtPathIsDir = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_fileExistsAtPathIsDir);
        }
    }

    // isReadableFileAtPath:
    {
        SEL sel = @selector(isReadableFileAtPath:);
        Method m = class_getInstanceMethod(fmCls, sel);
        if (m) {
            sOrig_isReadableFileAtPath = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_isReadableFileAtPath);
        }
    }

    // contentsOfDirectoryAtPath:error:
    {
        SEL sel = @selector(contentsOfDirectoryAtPath:error:);
        Method m = class_getInstanceMethod(fmCls, sel);
        if (m) {
            sOrig_contentsOfDirAtPath = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_contentsOfDirAtPath);
        }
    }

    // UIApplication canOpenURL:
    {
        SEL sel = @selector(canOpenURL:);
        Method m = class_getInstanceMethod([UIApplication class], sel);
        if (m) {
            sOrig_canOpenURL = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_canOpenURL);
        }
    }

    NSLog(@"[SpinLogger] Jailbreak bypass installed (v3 — %lu paths blocked)",
          (unsigned long)SLSuspiciousPaths().count);
}
