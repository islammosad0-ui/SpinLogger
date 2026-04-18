#import <UIKit/UIKit.h>

// ---------------------------------------------------------------------------
//  SLV4Panel — separate HUD for V4 hazard predictions
//
//  Shows:
//    - Header with active policy + cycle position t + agreement indicator
//    - Three policy rows (K5 / TRI / K10) each with fire light, prob value,
//      threshold, and ON/OFF state
//    - Footer with any-VT running catch rate + bets/catch this session
//
//  Interactions:
//    - Tap header: expand / collapse
//    - Tap a policy row: make it the "active" policy (drives bet-tier rec)
//    - Long-press header: toggle visibility
//    - Pan anywhere: drag window
//
//  Listens to SLSpinUpdateNotification (posted after each spin resolves +
//  features are updated) to refresh. Evaluates the policy engine each tick.
// ---------------------------------------------------------------------------

@interface SLV4Panel : NSObject
+ (instancetype)shared;
- (void)install;
- (void)show;
- (void)hide;
- (void)refresh;
@end

// Posted by the spin pipeline after feeding features. No object / userInfo.
extern NSString *const SLV4PanelRefreshNotification;
