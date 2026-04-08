#import "SLAccountID.h"

static NSString *const kAccountLabelKey = @"Speeder_AccountLabel";
static NSString *const kDefaultLabel = @"default";

NSString *SLSanitizedLabel(NSString *raw) {
    if (raw.length == 0) return kDefaultLabel;
    NSMutableString *out = [NSMutableString stringWithCapacity:raw.length];
    for (NSUInteger i = 0; i < raw.length; i++) {
        unichar c = [raw characterAtIndex:i];
        if ((c >= '0' && c <= '9') ||
            (c >= 'a' && c <= 'z') ||
            (c >= 'A' && c <= 'Z') ||
             c == '_' || c == '-') {
            [out appendFormat:@"%C", c];
        } else if (c == ' ') {
            [out appendString:@"_"];
        }
        // Everything else dropped
    }
    if (out.length == 0) return kDefaultLabel;
    // Limit to 32 chars
    if (out.length > 32) return [out substringToIndex:32];
    return [out copy];
}

NSString *SLAccountLabel(void) {
    NSString *stored = [[NSUserDefaults standardUserDefaults] stringForKey:kAccountLabelKey];
    if (stored.length > 0) return stored;
    return kDefaultLabel;
}

void SLSetAccountLabel(NSString *label) {
    NSString *clean = SLSanitizedLabel(label);
    [[NSUserDefaults standardUserDefaults] setObject:clean forKey:kAccountLabelKey];
    NSLog(@"[SpinLogger] Account label set to: %@", clean);
}
