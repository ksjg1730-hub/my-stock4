ValueError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/my-stock4/app.py", line 53, in <module>
    df = generate_silver_data()
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/runtime/caching/cache_utils.py", line 280, in __call__
    return self._get_or_create_cached_value(args, kwargs, spinner_message)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/runtime/caching/cache_utils.py", line 325, in _get_or_create_cached_value
    return self._handle_cache_miss(cache, value_key, func_args, func_kwargs)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.14/site-packages/streamlit/runtime/caching/cache_utils.py", line 384, in _handle_cache_miss
    computed_value = self._info.func(*func_args, **func_kwargs)
File "/mount/src/my-stock4/app.py", line 15, in generate_silver_data
    times = pd.date_range(start="2026-05-01", periods=200, freq='10T')
File "/home/adminuser/venv/lib/python3.14/site-packages/pandas/core/indexes/datetimes.py", line 1442, in date_range
    freq = to_offset(freq)
File "pandas/_libs/tslibs/offsets.pyx", line 6229, in pandas._libs.tslibs.offsets.to_offset
File "pandas/_libs/tslibs/offsets.pyx", line 6352, in pandas._libs.tslibs.offsets.to_offset
File "pandas/_libs/tslibs/offsets.pyx", line 6137, in pandas._libs.tslibs.offsets.raise_invalid_freq
