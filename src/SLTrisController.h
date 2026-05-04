#import <Foundation/Foundation.h>

// Bitmask for visible columns (bit 0 = attack, 1 = steal, 2 = spins, 3 = shield, 4 = accum, 5 = potion, 6 = vt)
#define kSLTrisColAttack  (1 << 0)
#define kSLTrisColSteal   (1 << 1)
#define kSLTrisColSpins   (1 << 2)
#define kSLTrisColShield  (1 << 3)
#define kSLTrisColAccum   (1 << 4)
#define kSLTrisColPotion  (1 << 5)
#define kSLTrisColVT      (1 << 6)
#define kSLTrisColAll     0x7F

@interface SLTrisController : NSObject
@property (nonatomic, copy) NSString *lockTarget;
@property (nonatomic, assign) BOOL skipEnabled;
@property (nonatomic, assign) NSUInteger visibleColumns; // bitmask of kSLTrisCol*
@property (nonatomic, readonly) BOOL isMonitorVisible;
+ (instancetype)shared;
- (void)install;
- (void)showTrisMonitor;
- (void)hideTrisMonitor;
- (void)toggleColumn:(NSUInteger)colBit;
// Called by counter overlay when a triple is hit
- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance;
- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance symbolCount:(NSInteger)symCount;
@end
