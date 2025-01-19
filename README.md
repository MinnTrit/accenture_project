### Sample video
https://github.com/user-attachments/assets/776a27cf-58cb-48a5-80cc-cead934bb87a

### Overall diagram
![image](https://github.com/user-attachments/assets/ae68a876-b113-49b3-8c80-1d98317ffd16)

### Diagram breakdown
* ```Step1```: User upload cookies from 1 browser and list of countries to scrape the data to the server
* ```Step2```: Flask application instance sends messages to the redbeat scheduler and the redis message broker
* ```Step3```: Clery application instance listening on the redis message broker will pick up the task and perform immediate execution of the task, the result of the task will be pasted to the spreadsheets to build the reports
* ```Step4```: The redbeat scheduler will schedule the task's configurations starting from the 2nd time of the same task-id => Starting from the 2nd time, the redbeat scheduler will send these parameters to the redis message broker in place of the Flask application instance

