#import <Foundation/Foundation.h>
#import "SLSpinParser.h"

void SLSpinStoreAppend(SLSpinResult *result);
NSString *SLSpinStoreCSVPath(void);
NSInteger SLSpinStoreCount(void);

// Rotate to a new CSV file (called on reset — starts a fresh session)
void SLSpinStoreRotateCSV(void);
