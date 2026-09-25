// Synthetic Swift-generated-style header for offline checker unit tests only.
// This fixture is not compiler output and does not establish iOS compilation.
#if defined(__OBJC__)
SWIFT_CLASS_NAMED("RowndBridge")
@interface RWNRowndBridge : NSObject
- (void)configureWithAppKey:(NSString * _Nonnull)appKey
                apiDomain:(NSString * _Nonnull)apiDomain
              apiBasePath:(NSString * _Nonnull)apiBasePath
                   hubURL:(NSString * _Nonnull)hubURL
                   scheme:(NSString * _Nonnull)scheme
               completion:(void (^ _Nonnull)(NSString * _Nullable))completion;
- (void)setStateListener:(void (^ _Nullable)(BOOL, BOOL, NSString * _Nullable))listener;
- (void)requestSignIn;
- (void)signOut;
- (void)getAccessToken:(void (^ _Nonnull)(NSString * _Nullable, NSString * _Nullable))completion;
- (BOOL)handleURL:(NSURL * _Nonnull)url SWIFT_WARN_UNUSED_RESULT;
- (void)dispose;
@end
#endif
