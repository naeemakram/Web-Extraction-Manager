# Web Extraction Manager Strategy

This document explains the strategy for testing the Web Extraction Manager system.

**System Architecture:**  
Web extraction manager is a client/server application. The client side is a browser based web application(the UI layer). The server side is an API layer which allows the users to create and run jobs through REST API calls. The API layer also keeps track of a user’s monthly job allowance(credits) and how much they’ve spent. If they run out of credit, they can’t start a job.  
I’ve designed a testing strategy based on the system architecture.

**Testing strategy:**  
The API layer is the heart of this application. That’s why we’re going to focus most of our testing efforts on the API layer. But within the API layer, the business logic will be encapsulated in services invoked by the API endpoints. This allows the core logic to be unit tested directly without going through HTTP.  
The API layer will be tested through unit and integration tests. The UI layer will be covered by end-to-end tests.  
Automated smoke testing will cover the UI layer. We’ll also perform data isolation testing on the UI layer.

**Important decisions:**  
The system will have the following limits

1. USER\_MAX\_JOBS: The maximum number of jobs a single user can run at once.  
2. SYSTEM\_MAX\_JOBS: The maximum number of jobs all users can run at once.

The system will decide whether to start a new job or not based on the two max numbers listed above.  
One credit will be subtracted against each page processed by our system. Credits won’t be reversed after a job is stopped.  
The system will not have a persistent data-storage.  
