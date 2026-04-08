#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLAccountID — user-settable account label used to name CSV files.
//
//  Default: "default"
//  User can change via Debt tile long-press → "Set Account Label".
//  Stored in NSUserDefaults key "Speeder_AccountLabel".
//  Sanitized to filesystem-safe characters (alphanumerics + underscores).
// ---------------------------------------------------------------------------

NSString *SLAccountLabel(void);
void SLSetAccountLabel(NSString *label);
NSString *SLSanitizedLabel(NSString *raw);
