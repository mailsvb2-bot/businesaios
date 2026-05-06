# runtime/boot

Role:
- concrete runtime assembly and boot wiring
- world-model verification
- explicit construction of concrete runtime services

Canonical rule:
- concrete `DecisionCore` construction is allowed only here
- runtime code outside boot should depend on ports / gateways, not raw boot-time concrete classes
