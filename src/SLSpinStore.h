#import <Foundation/Foundation.h>
#import "SLSpinParser.h"

void SLSpinStoreAppend(SLSpinResult *result);
NSString *SLSpinStoreCSVPath(void);
NSInteger SLSpinStoreCount(void);

// Rotate to a new CSV file (called on reset — starts a fresh session)
void SLSpinStoreRotateCSV(void);

// Call after changing the account label so the next append opens / creates
// the correctly-named file with a fresh header check (cheaper than RotateCSV —
// keeps the same session date and running counters).
void SLSpinStoreInvalidateHeader(void);
