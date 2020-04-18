import tensorflow as tf
import numpy as np
import random
from collections import deque
import cv2
import os
import sys
sys.path.append("game/")
import wrapped_flappy_bird as game
import time

# Hyper Parameters:
FRAME_PER_ACTION = 1
game_name = 'bird_TF_2013_2'    # the name of the game being played for log files
OBSERVE = 100.                  # timesteps to observe before training
EXPLORE = 150000.               # frames over which to anneal epsilon
FINAL_EPSILON = 0.0             # final value of epsilon
INITIAL_EPSILON = 0.01          # starting value of epsilon

model_path = "save_model/" + game_name
graph_path = "save_graph/" + game_name

# Make folder for save data
if not os.path.exists(model_path):
    os.makedirs(model_path)
if not os.path.exists(graph_path):
    os.makedirs(graph_path)

class DQNAgent:

    def __init__(self,action_size):
        # init replay memory
        self.memory = deque()
        # init some parameters
        self.time_step = 0
        self.epsilon = INITIAL_EPSILON
        self.action_size = action_size
        # init Q network
        self.build_model()
        self.batch_size = 32               # size of minibatch
        self.discount_factor = 0.99        # decay rate of past states
        self.size_replay_memory = 50000    # number of previous transitions to remember

    # def setInitState(self,state):
    #     self.stacked_state = np.stack((state, state, state, state), axis = 2)

    def conv2d(self,x, W, stride):
        return tf.nn.conv2d(x, W, strides = [1, stride, stride, 1], padding = "SAME")

    def weight_variable(self,shape):
        initial = tf.truncated_normal(shape, stddev = 0.01)
        return tf.Variable(initial)

    def bias_variable(self,shape):
        initial = tf.constant(0.01, shape = shape)
        return tf.Variable(initial)

    def max_pool_2x2(self,x):
        return tf.nn.max_pool(x, ksize = [1, 2, 2, 1], strides = [1, 2, 2, 1], padding = "SAME")

    def build_model(self):
        # network weights
        W_conv1 = self.weight_variable([8,8,4,32])
        b_conv1 = self.bias_variable([32])

        W_conv2 = self.weight_variable([4,4,32,64])
        b_conv2 = self.bias_variable([64])

        W_conv3 = self.weight_variable([3,3,64,64])
        b_conv3 = self.bias_variable([64])

        W_fc1 = self.weight_variable([1600,512])
        b_fc1 = self.bias_variable([512])

        W_fc2 = self.weight_variable([512,self.action_size])
        b_fc2 = self.bias_variable([self.action_size])

        # input layer

        self.stateInput = tf.placeholder("float",[None,80,80,4])

        # hidden layers
        h_conv1 = tf.nn.relu(self.conv2d(self.stateInput,W_conv1,4) + b_conv1)
        h_pool1 = self.max_pool_2x2(h_conv1)

        h_conv2 = tf.nn.relu(self.conv2d(h_pool1,W_conv2,2) + b_conv2)

        h_conv3 = tf.nn.relu(self.conv2d(h_conv2,W_conv3,1) + b_conv3)

        h_conv3_flat = tf.reshape(h_conv3,[-1,1600])
        h_fc1 = tf.nn.relu(tf.matmul(h_conv3_flat,W_fc1) + b_fc1)

        # Q Value layer
        self.output = tf.matmul(h_fc1,W_fc2) + b_fc2

        self.action_target = tf.placeholder("float",[None,self.action_size])
        self.y_target = tf.placeholder("float", [None]) 
        y_prediction = tf.reduce_sum(tf.multiply(self.output, self.action_target), reduction_indices = 1)
        self.Loss = tf.reduce_mean(tf.square(self.y_target - y_prediction))
        self.train_step = tf.train.AdamOptimizer(1e-6).minimize(self.Loss)

    def train_model(self):
        # Step 1: obtain random minibatch from replay memory
        minibatch   = random.sample(self.memory,self.batch_size)
        states      = [batch[0] for batch in minibatch]
        actions     = [batch[1] for batch in minibatch]
        rewards     = [batch[2] for batch in minibatch]
        next_states = [batch[3] for batch in minibatch]

        # Step 2: calculate y 
        y_array = []
        Q_array = self.output.eval(feed_dict={self.stateInput:next_states})
        for i in range(0,self.batch_size):
            done = minibatch[i][4]
            if done:
                y_array.append(rewards[i])
            else:
                y_array.append(rewards[i] + self.discount_factor * np.max(Q_array[i]))

        self.train_step.run(feed_dict={self.y_target : y_array, self.action_target : actions, self.stateInput : states})

    def get_action(self):
        Q_value = self.output.eval(feed_dict= {self.stateInput:[self.stacked_state]})[0]
        action = np.zeros(self.action_size)
        action_index = 0
        if self.time_step % FRAME_PER_ACTION == 0:
            if random.random() <= self.epsilon:
                action_index = random.randrange(self.action_size)
                action[action_index] = 1
            else:
                action_index = np.argmax(Q_value)
                action[action_index] = 1
        else:
            action[0] = 1 # do nothing

        # change episilon
        if self.epsilon > FINAL_EPSILON and self.time_step > OBSERVE:
            self.epsilon -= (INITIAL_EPSILON - FINAL_EPSILON)/EXPLORE

        return action

# preprocess raw image to 80*80 gray image
def preprocess(state):
    state = cv2.cvtColor(cv2.resize(state, (80, 80)), cv2.COLOR_BGR2GRAY)
    ret, state = cv2.threshold(state,1,255,cv2.THRESH_BINARY)
    return np.reshape(state,(80,80,1))


def main():
    # Step 1: init DQNAgent
    action_size = 2
    agent = DQNAgent(action_size)
    # saving and loading networks
    agent.saver = tf.train.Saver()
    agent.session = tf.InteractiveSession()
    agent.session.run(tf.initialize_all_variables())

    checkpoint = tf.train.get_checkpoint_state(model_path)        
    if checkpoint and checkpoint.model_checkpoint_path:
        agent.saver.restore(agent.session, checkpoint.model_checkpoint_path)
        print("\n\n Successfully loaded:", checkpoint.model_checkpoint_path,"\n\n")
    else:
        print("\n\n Could not find old network weights \n\n")
        
    # Step 2: init Flappy Bird Game
    game_state = game.GameState()
    # Step 3: play game
    
    # Step 3.1: obtain init state
    action = np.array([1,0])  # do nothing
    state, reward, done = game_state.frame_step(action)
    
    state = cv2.cvtColor(cv2.resize(state, (80, 80)), cv2.COLOR_BGR2GRAY)
    ret, state = cv2.threshold(state,1,255,cv2.THRESH_BINARY)
    # agent.setInitState(state)
    agent.stacked_state = np.stack((state, state, state, state), axis = 2)

    # Step 3.2: run the game
    start_time = time.time()
    time_step = 0
    episode = 0
    while time.time() - start_time < 5*60:
        time_step += 1
        episode_step = 0
        done = False
        while not done and episode_step < 1000:
            episode_step += 1
            action = agent.get_action()
            next_state, reward, done = game_state.frame_step(action)
            next_state = preprocess(next_state)

            #stacked_next_state = np.append(next_state,agent.stacked_state[:,:,1:],axis = 2)
            stacked_next_state = np.append(agent.stacked_state[:,:,1:],next_state,axis = 2)
            
            agent.memory.append((agent.stacked_state, action, reward, stacked_next_state, done))
            if len(agent.memory) > agent.size_replay_memory:
                agent.memory.popleft()
                
            if agent.time_step > OBSERVE:
                # Train the network
                agent.train_model()

            # update the old values
            agent.stacked_state = stacked_next_state
            agent.time_step += 1

            # print info
            progress = ""
            if agent.time_step <= OBSERVE:
                progress = "observe"
            elif agent.time_step > OBSERVE and agent.time_step <= OBSERVE + EXPLORE:
                progress = "explore"
            else:
                progress = "train"

            if done or episode_step == 1000:
                episode += 1
                print ("Episode :", episode, "/ Episode step :", episode_step, "/ STATE", progress, \
                       "/ EPSILON", agent.epsilon)
                break
            
    # save network every 100000 iteration
    # if agent.time_step % 1000 == 0:
    print("\n\n Now we save model \n\n")
    agent.saver.save(agent.session, model_path + "/bird-dqn", global_step = agent.time_step)

if __name__ == '__main__':
    main()