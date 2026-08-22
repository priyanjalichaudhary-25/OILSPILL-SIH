import cdsapi

c = cdsapi.Client()
c.retrieve(
    'reanalysis-era5-single-levels',
    {
        'product_type': 'reanalysis',
        'variable': ['10m_u_component_of_wind', '10m_v_component_of_wind'],
        'year': '2025',
        'month': '05',
        'day': ['24', '25', '26', '27', '28'],
        'time': [f'{h:02d}:00' for h in range(24)],
        'area': [10.6, 74.9, 8.0, 77.6],  # North, West, South, East
        'format': 'netcdf',
    },
    'data/wind_kerala_demo.nc'
)