# UI Locking (Two-Stage Rerun) Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Ensure the edge slider reflects the "disabled" state *immediately* when analysis starts by using a two-stage rerun trigger.

**Architecture:** 
1. Button click sets a `start_analysis` trigger and calls `st.rerun()`.
2. On script re-entry, the "start_analysis" trigger sets `is_analyzing` to True.
3. The slider is rendered using the `is_analyzing` state (now correctly True).
4. The analysis logic executes, then clears `is_analyzing` and reruns to restore the UI.

**Tech Stack:** Streamlit (Python)

---

### Task 1: Refactor UI States and Triggers

**Files:**
- Modify: `c:\Users\fkaga\Documents\Yeni klasör\iddaa_value_bet\app.py:53-70`

**Step 1: Setup two-stage state logic**

```python
    # Initialize UI states
    if 'is_analyzing' not in st.session_state:
        st.session_state['is_analyzing'] = False
    
    # Check if analysis was just triggered
    if st.session_state.get('start_analysis', False):
        st.session_state['is_analyzing'] = True
        st.session_state['start_analysis'] = False
        # Do not rerun here; let the script continue to render the disabled slider
        
    # Edge Slider
    min_edge_pct = st.slider(
        "Minimum Beklenen Kâr (Edge) Oranı %", 
        min_value=0.0, max_value=30.0, value=5.0, step=1.0,
        disabled=st.session_state['is_analyzing']
    )
```

**Step 2: Update Button Trigger**

```python
    if 'bulten' in st.session_state:
        if st.button("Yapay Zeka ile Analiz Et", type="primary", disabled=st.session_state['is_analyzing']):
            st.session_state['start_analysis'] = True
            st.rerun() # Force top-to-bottom re-run to catch the 'start_analysis' flag
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat(ui): implement two-stage rerun trigger for reliable UI locking"
```

---

### Task 2: Analysis Execution Guard

**Files:**
- Modify: `c:\Users\fkaga\Documents\Yeni klasör\iddaa_value_bet\app.py:70-85`

**Step 1: Perform analysis only if is_analyzing is True**

```python
    # Logic to execute the analysis only when the state is set
    if st.session_state['is_analyzing'] and 'bulten' in st.session_state:
        try:
            with st.spinner("İşlem yapılıyor..."):
                value_bets_df = analyzer.analyze_fixtures(
                    st.session_state['bulten'], 
                    min_edge=min_edge_pct/100.0,
                    bankroll=BANKROLL
                )
                st.session_state['value_bets'] = value_bets_df
        except Exception as e:
            st.error(f"Hata: {e}")
        finally:
            st.session_state['is_analyzing'] = False
            st.rerun() # Restore the UI
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "fix(ui): move analysis logic to state-guarded block"
```
