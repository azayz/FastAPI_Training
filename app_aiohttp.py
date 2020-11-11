from fastapi import FastAPI
from pydantic import BaseModel
import requests

from tortoise.models import Model
from tortoise import fields
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.contrib.fastapi import register_tortoise
import aiohttp
import asyncio

app = FastAPI()

session = None

@app.on_event('startup')
async def startup_event() :
    global session
    session = aiohttp.ClientSession() 

@app.on_event('shutdown')
async def shutdown_event() :
    await session.close()

class City(Model) : 
    id = fields.IntField(pk=True)
    name = fields.CharField(50,unique=True)
    timezone = fields.CharField(50)

    def current_time(self) -> str :
        return ''

    @classmethod
    async def get_current_time(cls, obj, session) :
        async with session.get(f'http://worldtimeapi.org/api/timezone/{obj.timezone}') as response :
            result = await response.json()
            current_time = result["datetime"]
            obj.current_time = current_time

    class Pydantic_Meta :
        computed = ('current_time',)


city_pydantic = pydantic_model_creator(City,name='city')
city_in_pydantic = pydantic_model_creator(City,name='city_in',exclude_readonly=True)

db = []

@app.get('/')
def index() :
    return {'key' : 'value'}

@app.get('/cities') 
async def get_cities() :
    cities = await city_pydantic.from_queryset(City.all())

    tasks = []
    global session
    for city in cities :
        task = asyncio.create_task(City.get_current_time(city,session))  
        tasks.append(task)
    await asyncio.gather(*tasks)
    return cities

@app.get('/cities/{city_id}')
async def get_city(city_id : int) :
    return await city_pydantic.from_queryset_single(City.get(id=city_id))

@app.post('/cities')
async def addCity(city :city_in_pydantic) :
    city_obj = await City.create(**city.dict(exclude_unset=True))
    return await city_in_pydantic.from_tortoise_orm(city_obj)

@app.delete('/cities/{city_id}')
async def delete_city(city_id : int) :
    await City.filter(id=city_id).delete()   
    return {}

register_tortoise(
    app,
    db_url='sqlite://db.sqlite3',
    modules={'models' : ['app_aiohttp']},
    generate_schemas=True,
    add_exception_handlers=True
)