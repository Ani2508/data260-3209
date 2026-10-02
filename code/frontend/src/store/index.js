import { configureStore } from '@reduxjs/toolkit'
import trialsReducer from './trialsSlice'
import sponsorsReducer from './sponsorsSlice'

export const store = configureStore({
  reducer: {
    trials: trialsReducer,
    sponsors: sponsorsReducer,
  },
})
