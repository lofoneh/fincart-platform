package main

import (
    "github.com/gin-gonic/gin"
    "net/http"
)

func main() {
    r := gin.Default()

    r.GET("/analytics/total-sales", func(c *gin.Context) {
        // Placeholder value
        c.JSON(http.StatusOK, gin.H{"total_sales": 105000})
    })

    r.Run(":8082") // Runs on localhost:8082
}
