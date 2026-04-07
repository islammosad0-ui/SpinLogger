#import <Foundation/Foundation.h>
#import "SLSpinParser.h"

void SLSpinStoreAppend(SLSpinResult *result);
NSString *SLSpinStoreCSVPath(void);
NSInteger SLSpinStoreCount(void);

// Rotate to a new CSV file (called on reset — starts a fresh session)
void SLSpinStoreRotateCSV(void);

// Call after changing Speeder_AccountName so the next append opens / creates
// the correctly-named file with a fresh header check.
void SLSpinStoreInvalidateHeader(void);
