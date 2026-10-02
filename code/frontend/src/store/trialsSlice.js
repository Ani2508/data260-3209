import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import { errorMessage, http } from './http'

// ---------- Async thunks (axios -> FastAPI) ----------
export const fetchTrials = createAsyncThunk('trials/fetch', async (_, { rejectWithValue }) => {
  try {
    const { data } = await http.get('/trials', { params: { page: 1, page_size: 100 } })
    return data.items
  } catch (err) { return rejectWithValue(errorMessage(err)) }
})

export const createTrial = createAsyncThunk('trials/create', async (trial, { rejectWithValue }) => {
  try {
    const { data } = await http.post('/trials', trial)
    return data
  } catch (err) { return rejectWithValue(errorMessage(err)) }
})

export const updateTrial = createAsyncThunk('trials/update', async ({ id, trial }, { rejectWithValue }) => {
  try {
    const { data } = await http.put(`/trials/${id}`, trial)
    return data
  } catch (err) { return rejectWithValue(errorMessage(err)) }
})

export const deleteTrial = createAsyncThunk('trials/delete', async (id, { rejectWithValue }) => {
  try {
    await http.delete(`/trials/${id}`)
    return id
  } catch (err) { return rejectWithValue(errorMessage(err)) }
})

// ---------- Slice ----------
const trialsSlice = createSlice({
  name: 'trials',
  initialState: { items: [], status: 'idle', error: null, message: null },
  reducers: {
    clearTrials: (state) => { state.items = []; state.status = 'idle'; state.error = null },
    clearMessage: (state) => { state.message = null; state.error = null },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTrials.pending, (state) => { state.status = 'loading'; state.error = null })
      .addCase(fetchTrials.fulfilled, (state, action) => {
        state.status = 'succeeded'
        state.items = action.payload
      })
      .addCase(createTrial.fulfilled, (state, action) => {
        state.items.unshift(action.payload)
        state.message = `Trial #${action.payload.id} created`
      })
      .addCase(updateTrial.fulfilled, (state, action) => {
        const i = state.items.findIndex((t) => t.id === action.payload.id)
        if (i !== -1) state.items[i] = action.payload
        state.message = `Trial #${action.payload.id} updated`
      })
      .addCase(deleteTrial.fulfilled, (state, action) => {
        state.items = state.items.filter((t) => t.id !== action.payload)
        state.message = `Trial #${action.payload} deleted`
      })
      // any rejected trials/* thunk -> store the error message
      .addMatcher((a) => a.type.startsWith('trials/') && a.type.endsWith('/rejected'),
        (state, action) => {
          if (action.type === fetchTrials.rejected.type) state.status = 'failed'
          state.error = action.payload ?? action.error.message
        })
  },
})

export const { clearTrials, clearMessage } = trialsSlice.actions
export default trialsSlice.reducer
