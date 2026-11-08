export class ApiNotConfiguredError extends Error {
  constructor() {
    super('The forecasting API is not connected.')
    this.name = 'ApiNotConfiguredError'
  }
}
