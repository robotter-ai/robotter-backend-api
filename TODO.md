# Birdeye Backtesting Implementation TODO

## Data Sources
- [x] Implement BirdeyeOrderBookDataSource
- [x] Implement BirdeyeOHLCVDataSource
- [x] Add unit tests for data sources

## Backtesting Engine Integration
- [ ] Create BirdeyeBacktestingDataProvider
  - [ ] Implement get_candles_df method
  - [ ] Handle timestamp conversion for backtesting
  - [ ] Add trading rules support
  - [ ] Add trade fee schema support

## Strategy Implementation
- [ ] Update BollingerV1Controller
  - [ ] Fix DataFrame index/column naming issues
  - [ ] Ensure compatibility with backtesting engine
  - [ ] Add proper error handling for insufficient data

## Testing
- [ ] Add integration tests for backtesting workflow
  - [ ] Test with mock Birdeye service
  - [ ] Verify Bollinger Band calculations
  - [ ] Validate trading signals
  - [ ] Check PnL calculations

## API Endpoints
- [ ] Update /backtest endpoint
  - [ ] Add proper error handling
  - [ ] Validate input parameters
  - [ ] Return standardized response format

## Documentation
- [ ] Add API documentation
- [ ] Document backtesting configuration
- [ ] Add example usage
- [ ] Document trading rules and fees

## Future Improvements
- [ ] Add support for more technical indicators
- [ ] Implement position sizing
- [ ] Add risk management features
- [ ] Support multiple trading pairs
- [ ] Add performance metrics
  - [ ] Sharpe ratio
  - [ ] Maximum drawdown
  - [ ] Win rate
  - [ ] Profit factor
