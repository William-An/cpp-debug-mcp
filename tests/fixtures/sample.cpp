#include <iostream>
#include <vector>
#include <string>

int add(int a, int b) {
    return a + b;
}

std::string greet(const std::string& name) {
    return "Hello, " + name + "!";
}

int sum_vector(const std::vector<int>& v) {
    int total = 0;
    for (int i = 0; i < static_cast<int>(v.size()); ++i) {
        total += v[i];
    }
    return total;
}

int main() {
    int x = 10;
    int y = 20;
    int result = add(x, y);
    std::cout << "add: " << result << std::endl;

    std::string msg = greet("World");
    std::cout << msg << std::endl;

    std::vector<int> nums = {1, 2, 3, 4, 5};
    int total = sum_vector(nums);
    std::cout << "sum: " << total << std::endl;

    return 0;
}
