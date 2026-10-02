import { createAsyncThunk, createSlice } from '@reduxjs/toolkit'
import { errorMessage, http } from './http'

// Sponsors feed the dropdown on the Create / Update forms.
export const fetchSponsors = createAsyncThunk('sponsors/fetch', async (_, { rejectWithValue }) => {
  try {
    const { data } = await http.get('/sponsors', { params: { page: 1, page_size: 100 } })
    return data.items
  } catch (err) { return rejectWithValue(errorMessage(err)) }
})

const sponsorsSlice = createSlice({
  name: 'sponsors',
  initialState: { items: [], error: null },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchSponsors.fulfilled, (state, action) => { state.items = action.payload; state.error = null })
      .addCase(fetchSponsors.rejected, (state, action) => { state.error = action.payload })
  },
})

export default sponsorsSlice.reducer
